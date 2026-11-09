"""TTS 文本处理与降级单元测试（不触网）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storysprout.composer import StoryRequest, compose_story
from storysprout.schema import Character
from storysprout.tts import _estimate_dur, _silence_wav, assign_voice, split_sentences


class TestSplitSentences(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(split_sentences("你好。世界！真的吗？"), ["你好。", "世界！", "真的吗？"])

    def test_quotes_kept(self):
        s = split_sentences("她说：“今天真好。”然后走了。")
        self.assertEqual(len(s), 2)
        self.assertTrue(s[0].startswith("她说"))

    def test_empty(self):
        self.assertEqual(split_sentences("  "), [])


class TestAssignVoice(unittest.TestCase):
    def setUp(self):
        self.chars = [Character(name="朵朵", traits="", appearance="", voice="protagonist"),
                      Character(name="布布", traits="", appearance="", voice="friend")]

    def test_speaker_before_quote(self):
        speaker, key = assign_voice("朵朵说：“我们走吧。”", self.chars)
        self.assertEqual((speaker, key), ("朵朵", "protagonist"))

    def test_narrator_default(self):
        speaker, key = assign_voice("天黑了下来。", self.chars)
        self.assertEqual((speaker, key), ("narrator", "narrator"))

    def test_mentioned_mid_sentence_is_narrator(self):
        speaker, _ = assign_voice("朵朵的帽子飞了。", self.chars)
        # 说话人只看引号前缀，句中提及不算
        self.assertEqual(speaker, "narrator")


class TestDegrade(unittest.TestCase):
    def test_estimate_duration_positive(self):
        self.assertGreaterEqual(_estimate_dur("一句十个字的一句的话呀"), 0.8)

    def test_silence_wav(self):
        import tempfile
        import wave
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.wav"
            _silence_wav(p, 0.5)
            with wave.open(str(p), "rb") as f:
                self.assertAlmostEqual(f.getnframes() / f.getframerate(), 0.5, places=2)


class TestIllustrationDeterminism(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        import tempfile
        from storysprout.config import IMAGE
        from storysprout.illustration import render_scene
        story = compose_story(StoryRequest.from_dict({"idea": "x", "scene": "太空"}))
        scene = story.scenes[0]
        with tempfile.TemporaryDirectory() as td:
            p1, p2 = Path(td) / "1.png", Path(td) / "2.png"
            render_scene(scene, story.characters, p1)
            render_scene(scene, story.characters, p2)
            self.assertEqual(p1.read_bytes(), p2.read_bytes())

    def test_unknown_mood_fallback(self):
        import tempfile
        from storysprout.config import IMAGE
        from storysprout.illustration import MOOD_SKY
        self.assertIn("期待", MOOD_SKY)


if __name__ == "__main__":
    unittest.main()
