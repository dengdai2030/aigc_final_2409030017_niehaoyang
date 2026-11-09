"""命令行入口。

用法：
    python -m storysprout.cli "太空冒险" --protagonist 朵朵 --scene 太空
    python -m storysprout.cli --help
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storysprout.agent import CaseSpec, RulePlanner, StoryAgent


def main() -> int:
    p = argparse.ArgumentParser(description="故事精灵 StorySprout · 多模态故事创作 Agent")
    p.add_argument("idea", help="一句话故事创意")
    p.add_argument("--protagonist", default="小满", help="主角名字")
    p.add_argument("--age", type=int, default=6, help="主角年龄")
    p.add_argument("--scene", default="森林", help="世界/场景")
    p.add_argument("--theme", default="勇气与友谊", help="主题")
    p.add_argument("--n-scenes", type=int, default=6, help="场景数")
    p.add_argument("--tag", default="cli_case", help="产物命名前缀")
    p.add_argument("--planner", choices=["rule", "llm"], default="rule")
    p.add_argument("--intervene", action="append", default=[],
                   help="创作完成后的干预指令，可多次")
    args = p.parse_args()

    case = CaseSpec(idea=args.idea, protagonist=args.protagonist, age=args.age,
                    scene=args.scene, theme=args.theme, n_scenes=args.n_scenes,
                    tag=args.tag)
    agent = StoryAgent(planner=RulePlanner() if args.planner == "rule" else None)
    report = agent.run(case)
    for ins in args.intervene:
        report["intervene"] = agent.intervene(ins)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("trace:", agent.save_trace())
    print("log  :", agent.render_log())
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
