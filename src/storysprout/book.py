"""绘本排版：PIL 逐页绘制 → 多页 PDF。

页面结构：封面（标题+主角设定图）→ 逐场景图文页 → 寓意页。
"""
from __future__ import annotations

from pathlib import Path

from .config import IMAGE
from .schema import Story

PAGE_W, PAGE_H = 1240, 1754  # A4 150dpi


def _font(size: int):
    from PIL import ImageFont
    for name in ("msyh.ttc", "simsun.ttc", "simhei.ttf"):
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
    return lines


def _page(img, draw):
    return img, draw


def build_pdf(story: Story, image_dir: Path, out: Path) -> Path:
    from PIL import Image, ImageDraw

    pages: list[Image.Image] = []

    # 封面
    img = Image.new("RGB", (PAGE_W, PAGE_H), (252, 247, 238))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, PAGE_W, 16], fill=(255, 184, 120))
    title_font, sub_font = _font(88), _font(40)
    tw = d.textlength(story.title, font=title_font)
    d.text(((PAGE_W - tw) / 2, 150), story.title, font=title_font, fill=(90, 62, 40))
    cover = image_dir / "scene01.png"
    if cover.exists():
        cw, ch = 1000, 562
        img.paste(Image.open(cover).convert("RGB").resize((cw, ch)), ((PAGE_W - cw) // 2, 340))
    y = 980
    d.text(((PAGE_W - tw) / 2, y + 30), "主要角色", font=sub_font, fill=(120, 90, 60))
    y += 110
    for c in story.characters:
        d.text((200, y), f"· {c.name}：{c.traits}；{c.appearance}",
               font=_font(36), fill=(80, 70, 60))
        y += 70
    pages.append(img)

    # 场景页
    body_font, mood_font = _font(40), _font(30)
    for scene in story.scenes:
        img = Image.new("RGB", (PAGE_W, PAGE_H), (252, 247, 238))
        d = ImageDraw.Draw(img)
        src = image_dir / f"scene{scene.scene_id:02d}.png"
        if src.exists():
            cw, ch = 1060, 596
            img.paste(Image.open(src).convert("RGB").resize((cw, ch)), (90, 110))
        d.text((90, 760), f"第 {scene.scene_id} 幕 · {scene.mood}", font=mood_font,
               fill=(200, 120, 80))
        y = 840
        for ln in _wrap(scene.text, body_font, PAGE_W - 220):
            d.text((120, y), ln, font=body_font, fill=(60, 52, 46))
            y += 66
            if y > PAGE_H - 140:
                break
        pages.append(img)

    # 寓意页
    img = Image.new("RGB", (PAGE_W, PAGE_H), (252, 247, 238))
    d = ImageDraw.Draw(img)
    moral_font = _font(64)
    y = PAGE_H // 3
    d.text((PAGE_W / 2 - d.textlength("这个故事想说的是", font=moral_font) / 2, y - 120),
           "这个故事想说的是", font=moral_font, fill=(200, 120, 80))
    for ln in _wrap(f"「{story.moral}」", moral_font, PAGE_W - 320):
        tw = d.textlength(ln, font=moral_font)
        d.text(((PAGE_W - tw) / 2, y), ln, font=moral_font, fill=(90, 62, 40))
        y += 110
    pages.append(img)

    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:],
                  resolution=150.0)
    return out
