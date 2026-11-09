"""schema 校验单元测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storysprout.composer import StoryRequest, compose_story
from storysprout.schema import Character, Scene, Story, StorySchemaError


def _valid_story_dict():
    return compose_story(StoryRequest.from_dict({"idea": "测试创意", "scene": "太空"})).to_dict()


class TestStorySchema(unittest.TestCase):
    def test_valid_story_passes(self):
        story = Story.from_dict(_valid_story_dict())
        self.assertGreaterEqual(len(story.scenes), 4)
        self.assertTrue(story.title)
        self.assertTrue(story.moral)

    def test_missing_top_field(self):
        d = _valid_story_dict()
        del d["moral"]
        with self.assertRaises(StorySchemaError):
            Story.from_dict(d)

    def test_duplicate_scene_id(self):
        d = _valid_story_dict()
        d["scenes"][1]["scene_id"] = d["scenes"][0]["scene_id"]
        with self.assertRaises(StorySchemaError):
            Story.from_dict(d)

    def test_short_scene_text_rejected(self):
        d = _valid_story_dict()
        d["scenes"][0]["text"] = "太短了"
        with self.assertRaises(StorySchemaError):
            Story.from_dict(d)

    def test_scene_id_must_be_int(self):
        d = _valid_story_dict()
        d["scenes"][0]["scene_id"] = "abc"
        with self.assertRaises(StorySchemaError):
            Story.from_dict(d)

    def test_character_missing_field(self):
        with self.assertRaises(StorySchemaError):
            Character.from_dict({"name": "x", "traits": ""})

    def test_save_load_roundtrip(self):
        import tempfile
        story = Story.from_dict(_valid_story_dict())
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            story.save(p)
            story2 = Story.load(p)
        self.assertEqual(story.title, story2.title)
        self.assertEqual(len(story.scenes), len(story2.scenes))

    def test_hero_property(self):
        story = Story.from_dict(_valid_story_dict())
        self.assertEqual(story.hero, story.characters[0])


if __name__ == "__main__":
    unittest.main()
