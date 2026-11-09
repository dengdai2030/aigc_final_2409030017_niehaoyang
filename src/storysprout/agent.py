"""Agent 核心：规划 → 执行 → 观测 → 干预重算。

    observe(创意) → plan(拆步骤) → act(调工具) → observe(结果) → replan
                                              ↑                │
                                              └── 用户干预 ────┘

关键设计：
1. 规划器可插拔：RulePlanner（离线固定 DAG）/ LLMPlanner（在线拆步骤）；
2. 干预最小重算：FIELD_IMPACT 字段→工具映射 + DEPENDS 依赖图；
3. 全程留痕：每步工具/入参/耗时/产物写入 trace，可导出创作日志。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .composer import StoryRequest
from .tools import FIELD_IMPACT, ToolRegistry, TRACE_DIR, default_registry

logger = logging.getLogger("storysprout.agent")


@dataclass
class Step:
    idx: int
    tool: str
    args: dict
    status: str = "pending"          # pending/running/done/failed/skipped
    result: dict = field(default_factory=dict)
    error: str = ""
    elapsed: float = 0.0

    def summary(self) -> str:
        if self.status == "done":
            keys = [k for k in self.result if k != "images"]
            return "、".join(f"{k}={_short(self.result[k])}" for k in keys[:3])
        return self.error or self.status


def _short(v: Any, n: int = 70) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


@dataclass
class CaseSpec:
    """一次创作任务的输入。"""
    idea: str
    protagonist: str = "小满"
    age: int = 6
    scene: str = "森林"
    theme: str = "勇气与友谊"
    n_scenes: int = 6
    tag: str = "case"

    def request(self) -> dict:
        return {"idea": self.idea, "protagonist": self.protagonist, "age": self.age,
                "scene": self.scene, "theme": self.theme, "n_scenes": self.n_scenes}


# ---------------------------------------------------------------- 规划器
class RulePlanner:
    """离线规划：固定 DAG，参数依赖上一步产物。"""
    name = "rule"

    def plan(self, case: CaseSpec) -> list[Step]:
        return [
            Step(0, "search_materials", {"query": case.idea, "top_k": 3}),
            Step(1, "write_story", {"request": case.request(), "story_file": f"{case.tag}_story.json"}),
            Step(2, "illustrate", {"story_file": ""}),
            Step(3, "voice", {"story_file": "", "out_name": f"{case.tag}_audiobook.mp3"}),
            Step(4, "compose_video", {"timeline_file": "", "out_name": f"{case.tag}_video.mp4"}),
            Step(5, "build_book", {"story_file": "", "out_name": f"{case.tag}_book.pdf"}),
        ]


class LLMPlanner(RulePlanner):
    """在线规划：把工具清单交给模型，让它给出步骤序列（JSON）。"""
    name = "llm"

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def plan(self, case: CaseSpec) -> list[Step]:
        from .config import LLM
        if LLM.provider != "openai" or not LLM.api_key:
            logger.warning("未配置 LLM，回退到规则规划器")
            return super().plan(case)
        try:
            from .llm import LLMClient
            system = ("你是多模态内容生产 Agent 的规划器。只输出 JSON："
                      '{"steps":[{"tool":"工具名","reason":"为什么"}]}')
            user = (f"可用工具：\n{json.dumps(self.registry.schemas(), ensure_ascii=False)}\n\n"
                    f"用户创意：{case.idea}\n"
                    "给出从创意到「故事+配图+配音+短片+绘本」的最少步骤序列。")
            data = LLMClient().chat_json(system, user, tag="agent:plan")
            steps = [Step(i, s["tool"], {}) for i, s in enumerate(data.get("steps", []))]
            return steps or super().plan(case)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 规划失败（%s），回退规则规划器", exc)
            return super().plan(case)


# ---------------------------------------------------------------- Agent
class StoryAgent:
    def __init__(self, registry: ToolRegistry | None = None,
                 planner: RulePlanner | None = None) -> None:
        self.registry = registry or default_registry()
        self.planner = planner or RulePlanner()
        self.trace: list[dict] = []
        self.state: dict[str, Any] = {}
        self.case: CaseSpec | None = None
        self.on_event = None  # 回调（server 用于推送进度）：fn(kind, msg)

    # -- 主循环 --------------------------------------------------------
    def run(self, case: CaseSpec) -> dict:
        self.case = case
        self.state = {"idea": case.idea, "request": case.request()}
        steps = self.planner.plan(case)
        self._log("plan", f"规划器={self.planner.name}，共 {len(steps)} 步："
                          + " → ".join(s.tool for s in steps))
        for step in steps:
            self._resolve_args(step)
            self._exec(step)
            if step.status == "failed":
                self._log("abort", f"{step.tool} 失败，终止：{step.error}")
                break
        return self.report()

    def _resolve_args(self, step: Step) -> None:
        """把上一步产物接到下一步入参——Agent 的"记忆"。"""
        a = step.args
        if step.tool in ("illustrate", "voice") and not a.get("story_file"):
            a["story_file"] = self.state.get("story_file", "")
        if step.tool == "compose_video":
            a["timeline_file"] = a.get("timeline_file") or self.state.get("timeline", "")
        if step.tool == "build_book":
            a["story_file"] = a.get("story_file") or self.state.get("story_file", "")

    def _exec(self, step: Step) -> None:
        tool = self.registry.get(step.tool)
        step.status = "running"
        t0 = time.time()
        self._log("act", f"#{step.idx} {tool.name}({_short(step.args, 90)})")
        try:
            step.result = tool.fn(**step.args) or {}
            step.status = "done"
            for key, val in step.result.items():
                self.state[key] = val
        except Exception as exc:  # noqa: BLE001 —— Agent 必须兜住任何工具异常
            step.status = "failed"
            step.error = f"{type(exc).__name__}: {exc}"
            logger.exception("工具 %s 失败", step.tool)
        step.elapsed = round(time.time() - t0, 2)
        self._log("observe", f"#{step.idx} {step.tool} {step.status} {step.elapsed}s {step.summary()}")
        self.trace.append({**asdict(step), "summary": step.summary()})

    def _log(self, kind: str, msg: str) -> None:
        self.trace.append({"kind": kind, "msg": msg, "ts": round(time.time(), 3)})
        if self.on_event:
            self.on_event(kind, msg)
        logger.info("[%s] %s", kind, msg)

    # -- 用户干预 ------------------------------------------------------
    def intervene(self, instruction: str) -> dict:
        """中途干预：解析指令 → 改需求 → 只重跑受影响的下游工具。"""
        assert self.case is not None, "先运行 run() 才能干预"
        before = dict(self.state.get("request", self.case.request()))
        after, changed = self._parse(instruction, before)

        self._log("intervene", f"用户：{instruction}")
        if not changed:
            reason = "没听懂这条指令。试试：「把主角改成XX」「年龄改成7岁」「场景改成太空」「主题改成诚实」"
            self._log("reject", reason)
            return {"ok": False, "changed": {}, "reason": reason, "affected": []}

        self.state["request"] = after
        affected = self._affected(set(before) | set(after), changed)
        self._log("replan", f"变更字段：{changed}　受影响步骤：{affected}")

        # 改名：确定性全文替换（不重新创作），写入副本保留原故事
        if "protagonist" in changed:
            src = Path(self.state["story_file"])
            dst = src.with_name(f"{src.stem}_干预后.json")
            dst.write_text(src.read_text(encoding="utf-8")
                           .replace(before["protagonist"], after["protagonist"]),
                           encoding="utf-8")
            self.state["story_file"] = str(dst)
            self._log("rewrite", f"全文替换主角名：{before['protagonist']} → {after['protagonist']}")

        tag = f"{self.case.tag}_干预后"
        renews = {"story_file": f"{tag}_story.json"}
        for tool_name in affected:
            args: dict = {}
            if tool_name == "write_story":
                args = {"request": after, "story_file": renews["story_file"]}
            elif tool_name == "illustrate":
                args = {"story_file": ""}
            elif tool_name == "voice":
                args = {"story_file": "", "out_name": f"{tag}_audiobook.mp3"}
            elif tool_name == "compose_video":
                args = {"timeline_file": "", "out_name": f"{tag}_video.mp4"}
            elif tool_name == "build_book":
                args = {"story_file": "", "out_name": f"{tag}_book.pdf"}
            step = Step(99, tool_name, args)
            # 干预后 story_file 指向副本
            if tool_name != "write_story" and "story_file" in args and not args["story_file"]:
                args["story_file"] = self.state.get("story_file", "")
            # compose_video 的时间轴总是取最新一次 voice 的产物
            if tool_name == "compose_video" and not args.get("timeline_file"):
                args["timeline_file"] = self.state.get("timeline", "")
            self._exec(step)
        return {"ok": True, "changed": changed, "affected": affected, "output_tag": tag}

    @staticmethod
    def _parse(ins: str, req: dict) -> tuple[dict, dict]:
        req = dict(req)
        changed: dict[str, str] = {}
        patterns = [
            (r"主角(?:的名字)?(?:改成|叫|换成|是)[「“\"]?([^\s，,。「」”\"]{1,8})", "protagonist"),
            (r"(?:年龄|岁数)(?:改成|换成)\s*(\d{1,2})", "age"),
            (r"(?:场景|地点|世界)(?:改成|换成|换到|变成)[：:]?[「「\"”]?([^\s，,。「」\"”\"]{1,12})", "scene"),
            (r"主题(?:改成|换成)[「「\"”]?([^\s，,。「」\"”\"]{1,12})", "theme"),
        ]
        for pat, key in patterns:
            m = re.search(pat, ins)
            if m:
                val = m.group(1).strip()
                if key == "age":
                    val = int(val)
                if req.get(key) != val:
                    req[key] = val
                    changed[key] = val
        return req, changed

    @staticmethod
    def _affected(all_keys, changed: dict) -> list[str]:
        affected: list[str] = []
        for f in changed:
            for t in FIELD_IMPACT.get(f, []):
                if t not in affected:
                    affected.append(t)
        return affected

    # -- 报告与留痕 ----------------------------------------------------
    def report(self) -> dict:
        done = [t for t in self.trace if "tool" in t]
        return {
            "case": self.case.tag if self.case else "",
            "idea": self.state.get("idea"),
            "steps": len(done),
            "ok": bool(done) and all(t["status"] == "done" for t in done),
            "total_elapsed": round(sum(t["elapsed"] for t in done), 1),
            "artifacts": {k: v for k, v in self.state.items()
                          if k in ("story_file", "audio", "video", "book", "timeline")},
        }

    def save_trace(self, path: Path | None = None) -> Path:
        path = path or TRACE_DIR / f"trace_{self.case.tag if self.case else 'case'}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.trace, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def render_log(self, path: Path | None = None) -> Path:
        """trace → 人类可读的创作流程日志（Markdown）。"""
        path = path or TRACE_DIR / f"log_{self.case.tag if self.case else 'case'}.md"
        lines = [f"# 创作流程日志 · {self.case.tag if self.case else ''}", "",
                 f"- 用户创意：{self.state.get('idea')}",
                 f"- 规划器：{self.planner.name}", "",
                 "| # | 工具 | 耗时 | 状态 | 产物摘要 |", "|---|---|---|---|---|"]
        for t in self.trace:
            if "tool" not in t:
                continue
            art = (t["result"].get("video") or t["result"].get("audio")
                   or t["result"].get("book") or t["result"].get("story_file")
                   or t["result"].get("images") or "")
            if isinstance(art, list):
                art = f"{len(art)} 张"
            lines.append(f"| {t['idx']} | {t['tool']} | {t['elapsed']}s | {t['status']} | "
                         f"{Path(str(art)).name if art else ''} |")
        lines += ["", "## 决策与观察"]
        for t in self.trace:
            if t.get("kind") in ("plan", "act", "observe", "intervene", "replan",
                                 "rewrite", "reject", "abort"):
                lines.append(f"- **{t['kind']}** {t['msg']}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
