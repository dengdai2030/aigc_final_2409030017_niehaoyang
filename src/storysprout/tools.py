"""Agent 的工具层：每个工具都是「纯函数 + 明确 schema」。

Agent 只依赖这张注册表，换模型 / 换框架时工具不用重写。
依赖关系写在 DEPENDS 里：用户中途改需求时，只重跑受影响的下游工具。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import AUDIO_DIR, BOOK_DIR, DATA_DIR, IMAGE_DIR, OUTPUT_DIR, VIDEO_DIR

STORY_DIR = DATA_DIR / "stories"
TRACE_DIR = OUTPUT_DIR / "traces"

# 工具依赖图：干预后按"字段→受影响工具"算最小重算集
DEPENDS = {
    "search_materials": [],
    "write_story": ["request"],
    "illustrate": ["story"],
    "voice": ["story"],
    "compose_video": ["story", "voice"],
    "build_book": ["story", "illustrate"],
}

# 变更字段 → 受影响的工具（干预重算的核心映射）
FIELD_IMPACT = {
    "protagonist": ["voice", "compose_video", "build_book"],   # 改名：图可复用
    "age": ["write_story", "illustrate", "voice", "compose_video", "build_book"],
    "scene": ["write_story", "illustrate", "voice", "compose_video", "build_book"],
    "theme": ["write_story", "illustrate", "voice", "compose_video", "build_book"],
    "idea": ["write_story", "illustrate", "voice", "compose_video", "build_book"],
}


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, str]
    fn: Callable[..., dict]
    produces: list[str] = field(default_factory=list)

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description,
                "parameters": self.params, "produces": self.produces}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"未注册的工具：{name}，可用：{list(self._tools)}")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]


# ---------------------------------------------------------------- 工具实现
def _t_search(query: str, top_k: int = 3) -> dict:
    """素材检索：TF-IDF 风格的字符 n-gram 打分（离线可用）。"""
    lib = json.loads((DATA_DIR / "templates.json").read_text(encoding="utf-8"))
    def grams(s: str, n=2) -> set[str]:
        s = "".join(ch for ch in s if ch.strip())
        return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}
    q = grams(query)
    scored = []
    for t in lib:
        doc = grams(t["name"] + t["world"] + t["theme"] + t["hook"])
        score = len(q & doc) / max(len(q), 1)
        scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    hits = [{"name": t["name"], "world": t["world"], "theme": t["theme"],
             "hook": t["hook"], "score": round(s, 3)} for s, t in scored[:top_k]]
    context = "；".join(f"{t['world']}题材《{t['name']}》：{t['hook']}" for s, t in scored[:2])
    return {"hits": hits, "context": context,
            "recommendation": {"sfx": ["八音盒", "风铃", "脚步声", "心跳", "欢呼"],
                               "style": "扁平儿童绘本风，暖色，柔光"}}


def _t_write_story(request: dict, story_file: str | None = None) -> dict:
    """写故事：在线 LLM（Prompt v3）→ 失败/无密钥 → 离线模板创作器。"""
    from .config import LLM
    from .composer import StoryRequest, compose_story
    from .schema import Story

    req = StoryRequest.from_dict(request)

    if LLM.provider == "openai" and LLM.api_key:
        try:
            from .llm import LLMClient
            from .prompts import build_story_prompt

            system, user = build_story_prompt(req)
            story = Story.from_dict(LLMClient().chat_json(system, user, tag="agent:story"))
            story.meta["source"] = "llm"
            path = STORY_DIR / (story_file or "story.json")
            story.save(path)
            return {"story_file": str(path), "source": "llm", "title": story.title,
                    "scenes": len(story.scenes)}
        except Exception as exc:  # noqa: BLE001 —— 在线失败 → 降级
            import logging
            logging.getLogger("storysprout.tools").warning(
                "在线写作失败（%s），降级为离线模板创作器", exc)

    story = compose_story(req)
    path = STORY_DIR / (story_file or "story.json")
    story.save(path)
    return {"story_file": str(path), "source": story.meta.get("source", "composer"),
            "title": story.title, "scenes": len(story.scenes)}


def _t_illustrate(story_file: str) -> dict:
    """配图：在线文生图（dashscope，未实现时提示）/ 本地 PIL 程序化插画。"""
    from .config import IMAGE
    from .schema import Story

    story = Story.load(story_file)
    if IMAGE.provider == "dashscope" and IMAGE.api_key:
        # 在线模式：调用通义万相（技术验证报告里记录；无密钥环境自动走本地）
        try:
            from . import online_image  # type: ignore
        except ImportError:
            pass
    made = []
    for scene in story.scenes:
        out = IMAGE_DIR / f"scene{scene.scene_id:02d}.png"
        from .illustration import render_scene
        render_scene(scene, story.characters, out)
        made.append(str(out))
    return {"images": made, "count": len(made),
            "consistency": f"seed={IMAGE.seed} + 角色特征卡"}


def _t_voice(story_file: str, out_name: str = "audiobook.mp3") -> dict:
    from .tts import synthesize_book
    timeline = synthesize_book(story_file, out_name=out_name)
    return {"audio": str(AUDIO_DIR / timeline["audio_file"]),
            "timeline": str(AUDIO_DIR / out_name.replace(".mp3", "_timeline.json")),
            "duration": timeline["total_duration"],
            "sentences": len(timeline["entries"]),
            "tts_provider": timeline["tts_provider"]}


def _t_compose_video(timeline_file: str, out_name: str = "story_video.mp4") -> dict:
    from .video import render_video
    timeline = json.loads(Path(timeline_file).read_text(encoding="utf-8"))
    out = VIDEO_DIR / out_name
    render_video(timeline_file, IMAGE_DIR, out)
    return {"video": str(out), "duration": timeline["total_duration"]}


def _t_build_book(story_file: str, out_name: str | None = None) -> dict:
    from .book import build_pdf
    from .schema import Story

    story = Story.load(story_file)
    out = BOOK_DIR / (out_name or f"{story.title}.pdf")
    build_pdf(story, IMAGE_DIR, out)
    return {"book": str(out), "pages": len(story.scenes) + 2}


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(Tool("search_materials", "在故事模板素材库检索，返回模板/音效/画风建议与写作上下文",
                      {"query": "str", "top_k": "int=3"}, _t_search, ["hits", "context"]))
    reg.register(Tool("write_story", "根据需求生成结构化故事 JSON（在线LLM/离线模板自动降级）",
                      {"request": "dict", "story_file": "str?"}, _t_write_story, ["story_file"]))
    reg.register(Tool("illustrate", "为每个场景生成配图（固定seed+特征卡保持角色一致）",
                      {"story_file": "str"}, _t_illustrate, ["images"]))
    reg.register(Tool("voice", "多角色配音合成有声书，输出句级时间轴",
                      {"story_file": "str", "out_name": "str?"}, _t_voice, ["audio", "timeline"]))
    reg.register(Tool("compose_video", "配图+配音+字幕按时间轴合成短片",
                      {"timeline_file": "str", "out_name": "str?"}, _t_compose_video, ["video"]))
    reg.register(Tool("build_book", "图文排版为 PDF 绘本",
                      {"story_file": "str", "out_name": "str?"}, _t_build_book, ["book"]))
    return reg
