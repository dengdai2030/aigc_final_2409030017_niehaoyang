"""离线模板创作器单元测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storysprout.composer import StoryRequest, compose_story
from storysprout.schema import Story


class TestComposer(unittest.TestCase):
    def test_deterministic(self):
        req = StoryRequest.from_dict({"idea": "太空冒险", "scene": "太空"})
        a = compose_story(req).to_dict()
        b = compose_story(req).to_dict()
        self.assertEqual(a, b)

    def test_schema_pass_various_ideas(self):
        for idea, scene in [("太空冒险", "太空"), ("森林找路", "森林"),
                            ("深海珍珠", "海洋"), ("城市停电", "城市"),
                            ("沙漠绿洲", "沙漠"), ("未知世界xyz", "峡谷")]:
            with self.subTest(idea=idea):
                Story.from_dict(compose_story(
                    StoryRequest.from_dict({"idea": idea, "scene": scene})).to_dict())

    def test_protagonist_used(self):
        story = compose_story(StoryRequest.from_dict({"idea": "x", "protagonist": "朵拉"}))
        self.assertEqual(story.hero.name, "朵拉")
        self.assertIn("朵拉", story.scenes[0].text)

    def test_scene_count_clamped(self):
        story = compose_story(StoryRequest.from_dict({"idea": "x", "n_scenes": 99}))
        self.assertLessEqual(len(story.scenes), 6)

    def test_mood_arc_covers_six_beats(self):
        story = compose_story(StoryRequest.from_dict({"idea": "x", "n_scenes": 6}))
        moods = [s.mood for s in story.scenes]
        self.assertEqual(moods, ["好奇", "期待", "挑战", "低谷", "转机", "圆满"])

    def test_visual_prompt_mentions_hero(self):
        story = compose_story(StoryRequest.from_dict({"idea": "x", "protagonist": "朵朵"}))
        for s in story.scenes:
            self.assertIn("朵朵", s.visual_prompt)


if __name__ == "__main__":
    unittest.main()
