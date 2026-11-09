"""LLM JSON 修复与用量统计单元测试（不触网）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storysprout.llm import Usage, extract_json


class TestExtractJson(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_json('{"a": 1}')["a"], 1)

    def test_markdown_fence(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```')["a"], 1)

    def test_prose_wrapped(self):
        self.assertEqual(extract_json('好的，以下是结果：\n{"a": {"b": 2}}\n希望有帮助')["a"]["b"], 2)

    def test_trailing_comma(self):
        self.assertEqual(extract_json('{"a": [1, 2,],}')["a"], [1, 2])

    def test_fullwidth_quotes(self):
        self.assertEqual(extract_json('{"a“：“b”}').get("a"), "b")

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            extract_json("这不是JSON")

    def test_nested_braces_in_strings(self):
        self.assertEqual(extract_json('{"s": "包含 } 的字符串"}')["s"], "包含 } 的字符串")


class TestUsage(unittest.TestCase):
    def test_cost_accumulates(self):
        from storysprout.config import LLMConfig
        cfg = LLMConfig()
        u = Usage()
        u.add(1000, 500, cfg, "t")
        self.assertEqual(u.calls, 1)
        self.assertAlmostEqual(u.cost_cny, cfg.price_in_per_1k + 0.5 * cfg.price_out_per_1k)


if __name__ == "__main__":
    unittest.main()
