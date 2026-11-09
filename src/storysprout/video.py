"""短片合成：图片 + 配音 + 字幕 → MP4。

方法：按时间轴把每句话的画面帧（对应场景图 + PIL 烧录字幕）
写成 ffmpeg concat 列表，一次合成，天然音画同步（同一时间轴驱动）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import IMAGE

logger = logging.getLogger("storysprout.video")


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _load_font(size: int):
    from PIL import ImageFont
    for name in ("msyh.ttc", "msyhbd.ttc", "simsun.ttc", "simhei.ttf"):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or [text]


def _frame(src: Path, caption: str, out: Path) -> None:
    from PIL import Image, ImageDraw

    w, h = IMAGE.size
    img = Image.open(src).convert("RGB").resize((w, h))
    draw = ImageDraw.Draw(img, "RGBA")
    if caption:
        font = _load_font(34)
        lines = _wrap(caption, font, w - 160)
        lh = 48
        block_h = len(lines) * lh + 30
        y0 = h - block_h - 34
        draw.rounded_rectangle([70, y0, w - 70, y0 + block_h], radius=18,
                               fill=(20, 18, 28, 170))
        y = y0 + 18
        for ln in lines:
            tw = draw.textlength(ln, font=font)
            draw.text(((w - tw) / 2, y), ln, font=font, fill=(255, 250, 240))
            y += lh
    img.save(out, "JPEG", quality=88)


def render_video(timeline_path: str | Path, image_dir: Path, out: Path) -> Path:
    """timeline.json + 场景图 → 短片。"""
    timeline = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
    frame_dir = Path(timeline_path).parent / "_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    scene_of = {}
    list_path = frame_dir / "list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for i, e in enumerate(timeline["entries"]):
            scene_of.setdefault(e["scene_id"], image_dir / f"scene{e['scene_id']:02d}.png")
            frame = frame_dir / f"f{i:04d}.jpg"
            _frame(scene_of[e["scene_id"]], e["text"], frame)
            # 句间停顿并入下一句起始：每帧时长 = dur + gap（最后一句不含）
            gap = 0.28 if i < len(timeline["entries"]) - 1 else 0.5
            f.write(f"file '{frame.as_posix()}'\nduration {e['dur'] + gap:.3f}\n")
        f.write(f"file '{frame.as_posix()}'\n")  # concat 要求末尾重复最后一帧

    audio = Path(timeline_path).parent / timeline["audio_file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg(), "-y", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", str(list_path),
           "-i", str(audio),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "160k",
           "-shortest", "-movflags", "+faststart", str(out)]
    subprocess_run(cmd)
    return out


def subprocess_run(cmd: list[str]) -> None:
    import subprocess
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败：{res.stderr[-400:]}")
