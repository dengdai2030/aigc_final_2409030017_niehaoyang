"""多角色配音：edge-tts + 句级时间轴。

流程：story.json → 逐句分派（角色→音色，mood→语速/音调）→
逐句合成（每句重试 2 次）→ WAV 拼接 → MP3 → timeline.json。

可靠性设计（第 13 周测试报告的修复项）：
- 单句失败只降级该句（按字数估算时长 + 静音占位），不污染全局；
- 连续 3 句失败才判定网络不可用，后续句子直接走本地估算；
- 停顿用本地生成的静音 WAV，不消耗 API 调用。

时间轴是"模态间关联"的枢纽：视频字幕对齐、网页高亮都读它。
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import struct
import subprocess
import time
import wave
from pathlib import Path

from .config import AUDIO_DIR, TTS

logger = logging.getLogger("storysprout.tts")

MOOD_PARAMS = {
    "好奇": ("-4%", "+0Hz"), "期待": ("+4%", "+0Hz"),
    "挑战": ("+10%", "+4Hz"), "低谷": ("-12%", "-4Hz"),
    "转机": ("+2%", "+2Hz"), "圆满": ("-2%", "+2Hz"),
}

RATE = 22050  # 全流程统一的 WAV 采样率
GAP = 0.28    # 句间停顿（秒）


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def assign_voice(sentence: str, characters) -> tuple[str, str]:
    """返回 (角色名, voice_key)。说话人在引号前出现则归给他，否则旁白。"""
    for ch in characters:
        if ch.name in sentence.split("“")[0].split("\"")[0]:
            return ch.name, ch.voice
    return "narrator", "narrator"


def _synth_once(text: str, voice: str, rate: str, pitch: str, mp3: Path, wav: Path) -> float:
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(mp3)))
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(mp3),
                    "-ar", str(RATE), "-ac", "1", str(wav)],
                   check=True, capture_output=True)
    with wave.open(str(wav), "rb") as f:
        return round(f.getnframes() / f.getframerate(), 3)


def _silence_wav(path: Path, dur: float) -> None:
    n = int(RATE * dur)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(b"\x00\x00" * n)


def _estimate_dur(text: str) -> float:
    return round(max(len(text) / 4.2, 0.8), 3)


def _make_bgm(total: float, out: Path, volume: float = 0.05) -> None:
    """程序化八音盒 BGM：C 大调五声音阶琶音，低音量铺底。"""
    notes = [523.25, 587.33, 659.25, 783.99, 880.00, 659.25, 587.33, 523.25]
    note_len = int(RATE * 1.5)
    n = int(RATE * total)
    frames = bytearray()
    for i in range(n):
        phase = (i % note_len) / RATE
        idx = (i // note_len) % len(notes)
        env = math.exp(-1.6 * phase)
        val = volume * env * math.sin(2 * math.pi * notes[idx] * phase)
        frames += struct.pack("<h", int(val * 32767))
    with wave.open(str(out), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(bytes(frames))


def synthesize_book(story_path: str | Path, out_name: str = "audiobook.mp3",
                    bgm: bool = True) -> dict:
    """把整本故事合成为有声书，返回 timeline dict。"""
    from .schema import Story

    story = Story.load(story_path)
    seg_dir = AUDIO_DIR / "_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    for old in seg_dir.glob("*.wav"):
        old.unlink()

    online = TTS.provider == "edge"
    consecutive_fail = 0
    entries: list[dict] = []
    t = 0.0

    for scene in story.scenes:
        rate, pitch = MOOD_PARAMS.get(scene.mood, ("+0%", "+0Hz"))
        for sent in split_sentences(scene.text):
            speaker, voice_key = assign_voice(sent, story.characters)
            voice = TTS.voice_map.get(voice_key, TTS.voice_map["narrator"])
            idx = len(entries)
            wav = seg_dir / f"s{idx:04d}.wav"
            dur = 0.0
            if online and consecutive_fail < 3:
                for attempt in range(2):  # 每句最多重试 2 次
                    try:
                        dur = _synth_once(sent, voice, rate, pitch,
                                          wav.with_suffix(".mp3"), wav)
                        consecutive_fail = 0
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("句子 %d 第 %d 次合成失败：%s", idx + 1, attempt + 1, exc)
                else:
                    consecutive_fail += 1
            if dur == 0.0:
                dur = _estimate_dur(sent)
                _silence_wav(wav, dur)
            entries.append({
                "scene_id": scene.scene_id, "text": sent, "speaker": speaker,
                "voice": voice, "rate": rate, "pitch": pitch,
                "start": round(t, 3), "dur": dur,
            })
            t += dur + GAP

    total = round(t, 2)

    # 拼接：句子 WAV + 0.28s 静音，一次 concat 后统一编码 MP3
    if any((seg_dir / f"s{i:04d}.wav").exists() for i in range(len(entries))):
        pause = seg_dir / "_pause.wav"
        _silence_wav(pause, GAP)
        concat_list = seg_dir / "list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for i in range(len(entries)):
                f.write(f"file '{(seg_dir / f's{i:04d}.wav').as_posix()}'\n")
                if i < len(entries) - 1:
                    f.write(f"file '{pause.as_posix()}'\n")
        mp3 = AUDIO_DIR / out_name
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat",
                        "-safe", "0", "-i", str(concat_list),
                        "-c:a", "libmp3lame", "-q:a", "4", str(mp3)],
                       check=True, capture_output=True)
    else:
        mp3 = AUDIO_DIR / out_name
        _silence_wav(mp3.with_suffix(".wav"), total)
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error",
                        "-i", str(mp3.with_suffix(".wav")),
                        "-c:a", "libmp3lame", "-q:a", "4", str(mp3)],
                       check=True, capture_output=True)

    if bgm:
        bgm_wav = AUDIO_DIR / "_bgm.wav"
        _make_bgm(total + 0.5, bgm_wav)
        mixed = AUDIO_DIR / out_name.replace(".mp3", "_tmp.mp3")
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(mp3),
                        "-i", str(bgm_wav), "-filter_complex",
                        "[1:a]volume=0.45[b];[0:a][b]amix=inputs=2:duration=first",
                        "-c:a", "libmp3lame", "-q:a", "4", str(mixed)],
                       check=True, capture_output=True)
        mp3.unlink(missing_ok=True)
        mixed.rename(mp3)

    timeline = {"audio_file": mp3.name, "total_duration": total,
                "title": story.title, "entries": entries,
                "tts_provider": "edge" if online and consecutive_fail < 3 else "off",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    tl_path = AUDIO_DIR / out_name.replace(".mp3", "_timeline.json")
    tl_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return timeline
