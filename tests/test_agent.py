"""Agent 干预逻辑单元测试（纯逻辑，不触网）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storysprout.agent import CaseSpec, RulePlanner, StoryAgent
from storysprout.tools import DEPENDS, FIELD_IMPACT


class TestInterveneParse(unittest.TestCase):
    REQ = {"idea": "x", "protagonist": "朵朵", "age": 6, "scene": "太空", "theme": "勇气"}

    def test_rename(self):
        _, changed = StoryAgent._parse("把主角改成朵拉", self.REQ)
        self.assertEqual(changed, {"protagonist": "朵拉"})

    def test_rename_with_quotes(self):
        _, changed = StoryAgent._parse("主角改成“小树”", self.REQ)
        self.assertEqual(changed, {"protagonist": "小树"})

    def test_age(self):
        _, changed = StoryAgent._parse("年龄改成7岁", self.REQ)
        self.assertEqual(changed, {"age": 7})
        self.assertIsInstance(changed["age"], int)

    def test_scene(self):
        _, changed = StoryAgent._parse("场景改成森林", self.REQ)
        self.assertEqual(changed, {"scene": "森林"})

    def test_unrecognized_instruction(self):
        _, changed = StoryAgent._parse("今天天气不错", self.REQ)
        self.assertEqual(changed, {})

    def test_no_change_when_same(self):
        _, changed = StoryAgent._parse("主角改成朵朵", self.REQ)
        self.assertEqual(changed, {})


class TestMinimalRecompute(unittest.TestCase):
    def test_rename_recompute_set(self):
        self.assertEqual(FIELD_IMPACT["protagonist"],
                         ["voice", "compose_video", "build_book"])

    def test_scene_recompute_is_full_chain(self):
        self.assertIn("write_story", FIELD_IMPACT["scene"])
        self.assertIn("illustrate", FIELD_IMPACT["scene"])

    def test_depends_graph_consistent(self):
        for tool, deps in DEPENDS.items():
            self.assertIsInstance(deps, list)
        self.assertIn("voice", DEPENDS["compose_video"])

    def test_affected_dedup_and_order(self):
        out = StoryAgent._affected(set(), {"scene": "森林", "age": 7})
        self.assertEqual(len(out), len(set(out)))
        self.assertEqual(out[0], "write_story")


class TestPlanner(unittest.TestCase):
    def test_rule_planner_six_steps(self):
        steps = RulePlanner().plan(CaseSpec(idea="x"))
        self.assertEqual([s.tool for s in steps],
                         ["search_materials", "write_story", "illustrate",
                          "voice", "compose_video", "build_book"])


if __name__ == "__main__":
    unittest.main()
