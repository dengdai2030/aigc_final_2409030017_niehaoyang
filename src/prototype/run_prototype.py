"""第11周 · 技术验证原型：一条命令跑通端到端核心流程。

创意 → 检索 → 写作 → 配图 → 配音 → 短片 → 绘本，产物全部落在 outputs/。
用法：python src/prototype/run_prototype.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from storysprout.agent import CaseSpec, RulePlanner, StoryAgent


def main() -> int:
    case = CaseSpec(
        idea="一段关于勇气的小小太空冒险",
        protagonist="朵朵", age=6, scene="太空", theme="勇气与友谊",
        n_scenes=6, tag="prototype",
    )
    t0 = time.time()
    agent = StoryAgent(planner=RulePlanner())
    report = agent.run(case)
    report["wall_clock_s"] = round(time.time() - t0, 1)
    agent.save_trace(ROOT / "outputs/traces/trace_prototype.json")
    agent.render_log(ROOT / "outputs/traces/log_prototype.md")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n=== 原型端到端结束 ===")
    for k, v in report["artifacts"].items():
        print(f"  {k}: {v}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
