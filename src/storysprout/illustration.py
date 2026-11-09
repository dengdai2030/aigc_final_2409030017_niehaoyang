"""插画生成：在线文生图 / 本地 PIL 程序化插画（离线降级）。

本地插画的角色一致性方案：全局固定 seed + 角色特征卡（palette 颜色、
体型比例、位置锚点）。同一角色在任意场景中发色/服装色/比例完全一致，
场景差异只来自背景图层。在线模式（dashscope）留给有密钥的环境。
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from .config import IMAGE
from .schema import Character, Scene

# mood → (天空上色, 天空下色, 光源色)
MOOD_SKY = {
    "好奇": ((255, 236, 201), (255, 214, 165), (255, 196, 120)),
    "期待": ((173, 216, 230), (255, 244, 214), (255, 236, 160)),
    "挑战": ((74, 89, 128), (150, 140, 170), (200, 200, 220)),
    "低谷": ((90, 82, 110), (222, 170, 135), (240, 180, 120)),
    "转机": ((255, 183, 120), (255, 224, 178), (255, 210, 130)),
    "圆满": ((63, 55, 100), (255, 160, 122), (255, 214, 145)),
}


def _hex(c: str, fallback=(120, 120, 120)) -> tuple:
    try:
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def _gradient(img, top, bottom):
    from PIL import ImageDraw
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)


def _draw_stars(draw, rng, w, h, n, color=(255, 255, 240)):
    for _ in range(n):
        x, y = rng.randint(0, w), rng.randint(0, int(h * 0.6))
        r = rng.choice([1, 1, 2])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _draw_hills(draw, rng, w, h, base_y, color):
    pts = [(0, h)]
    for x in range(0, w + 40, 40):
        pts.append((x, base_y + int(30 * math.sin(x / 120 + rng.random() * 0.5))))
    pts.append((w, h))
    draw.polygon(pts, fill=color)


def _draw_trees(draw, rng, w, base_y, color, n=5):
    for _ in range(n):
        x = rng.randint(20, w - 20)
        th = rng.randint(50, 110)
        draw.polygon([(x - th // 3, base_y), (x, base_y - th), (x + th // 3, base_y)], fill=color)
        draw.rectangle([x - 4, base_y, x + 4, base_y + 14], fill=(94, 68, 48))


def _draw_character(draw, cx, base_y, ch: Character, scale=1.0):
    """简单人物：圆头 + 梯形身体 + 手脚。颜色来自角色特征卡（一致性核心）。"""
    pal = ch.palette or {"hair": "#5b3a29", "cloth": "#ff8a65", "accent": "#ffd54f"}
    hair, cloth, accent = _hex(pal.get("hair")), _hex(pal.get("cloth")), _hex(pal.get("accent"))
    s = scale
    # 身体
    draw.rounded_rectangle([cx - 26 * s, base_y - 92 * s, cx + 26 * s, base_y],
                           radius=20 * s, fill=cloth)
    # 头
    head_r = 30 * s
    draw.ellipse([cx - head_r, base_y - 92 * s - head_r * 2 + 8 * s,
                  cx + head_r, base_y - 92 * s + 8 * s], fill=(255, 224, 196))
    # 头发
    draw.chord([cx - head_r, base_y - 92 * s - head_r * 2 + 8 * s,
                cx + head_r, base_y - 92 * s - head_r * 2 + 8 * s + head_r * 1.5],
               180, 360, fill=hair)
    # 眼睛与腮红
    ey = base_y - 92 * s - head_r * 0.7
    draw.ellipse([cx - 12 * s, ey, cx - 6 * s, ey + 8 * s], fill=(60, 50, 50))
    draw.ellipse([cx + 6 * s, ey, cx + 12 * s, ey + 8 * s], fill=(60, 50, 50))
    draw.ellipse([cx - 22 * s, ey + 6 * s, cx - 14 * s, ey + 12 * s], fill=(255, 170, 160))
    draw.ellipse([cx + 14 * s, ey + 6 * s, cx + 22 * s, ey + 12 * s], fill=(255, 170, 160))
    # 围巾点缀（accent）
    draw.rounded_rectangle([cx - 16 * s, base_y - 96 * s, cx + 16 * s, base_y - 84 * s],
                           radius=6 * s, fill=accent)
    # 腿脚
    draw.rounded_rectangle([cx - 16 * s, base_y, cx - 4 * s, base_y + 26 * s],
                           radius=5 * s, fill=(70, 62, 58))
    draw.rounded_rectangle([cx + 4 * s, base_y, cx + 16 * s, base_y + 26 * s],
                           radius=5 * s, fill=(70, 62, 58))


def _draw_friend(draw, cx, cy, ch: Character, scale=1.0):
    """光团伙伴：暖黄光晕 + 眨眼。"""
    pal = ch.palette or {"accent": "#ffd54f"}
    accent = _hex(pal.get("accent"), (255, 213, 79))
    r = 22 * scale
    draw.ellipse([cx - r * 1.9, cy - r * 1.9, cx + r * 1.9, cy + r * 1.9],
                 fill=(accent[0], accent[1], accent[2], ) if len(accent) == 3 else accent)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 244, 200))
    draw.ellipse([cx - r * 0.4, cy - r * 0.25, cx - r * 0.15, cy + r * 0.05], fill=(90, 70, 40))
    draw.ellipse([cx + r * 0.15, cy - r * 0.25, cx + r * 0.4, cy + r * 0.05], fill=(90, 70, 40))
    draw.chord([cx - r * 0.35, cy + r * 0.05, cx + r * 0.35, cy + r * 0.5], 20, 160, fill=(90, 70, 40))


def render_scene(scene: Scene, characters: list[Character], out: Path,
                 hero_index: int = 0) -> Path:
    """按场景渲染一张 1280x720 插画（确定性：seed = IMAGE.seed + scene_id）。"""
    from PIL import Image, ImageDraw

    w, h = IMAGE.size
    rng = random.Random(IMAGE.seed + scene.scene_id * 1009)
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    top, bottom, light = MOOD_SKY.get(scene.mood, MOOD_SKY["期待"])
    _gradient(img, top, bottom)
    draw = ImageDraw.Draw(img, "RGBA")

    vp = scene.visual_prompt + scene.description
    is_night = any(k in vp for k in ("夜", "星空", "星", "紫金"))
    is_space = "太空" in vp or "星际" in vp or "行星" in vp
    is_sea = "深海" in vp or "海洋" in vp or "珊瑚" in vp
    is_city = "城市" in vp or "路灯" in vp

    if is_space or is_night:
        _draw_stars(draw, rng, w, h, 90)
    if is_space:
        draw.ellipse([w - 260, 60, w - 100, 220], fill=(214, 158, 122))
        draw.ellipse([w - 285, 120, w - 75, 160], outline=(255, 255, 255), width=4)
    elif is_night:
        draw.ellipse([w - 220, 70, w - 140, 150], fill=(255, 240, 200))
    else:
        draw.ellipse([90, 60, 190, 160], fill=light)

    ground = int(h * 0.72)
    if is_sea:
        for i in range(6):
            y0 = ground + i * 16
            draw.arc([-60 + i * 30, y0, w + 60, y0 + 60], 200, 340,
                     fill=(255, 255, 255, 60), width=3)
        draw.rectangle([0, ground + 90, w, h], fill=(30, 60, 90))
    elif is_city:
        rng2 = random.Random(IMAGE.seed + 7)
        x = 0
        while x < w:
            bw, bh = rng2.randint(70, 130), rng2.randint(120, 260)
            draw.rectangle([x, ground - bh + 60, x + bw, h], fill=(52, 48, 76))
            for wx in range(x + 10, x + bw - 10, 22):
                for wy in range(ground - bh + 80, ground + 40, 30):
                    if rng2.random() < 0.5:
                        draw.rectangle([wx, wy, wx + 10, wy + 12], fill=(255, 220, 130))
            x += bw + 12
    else:
        _draw_hills(draw, rng, w, h, ground - 30, (126, 168, 108))
        _draw_hills(draw, random.Random(IMAGE.seed + 3), w, h, ground + 40, (94, 140, 86))
        _draw_trees(draw, rng, w, ground + 8, (66, 112, 72))

    # 地面
    draw.rectangle([0, h - 56, w, h], fill=(70, 120, 76) if not (is_sea or is_space or is_city)
                   else ((20, 44, 66) if is_sea else (46, 40, 70) if is_space or is_city else (70, 120, 76)))

    # 角色：主角居中（固定锚点 → 一致性），伙伴在侧上方
    hero = characters[hero_index] if characters else None
    if hero:
        _draw_character(draw, w // 2 - 60, h - 120, hero, scale=1.15)
    if len(characters) > 1:
        _draw_friend(draw, w // 2 + 150, int(h * 0.42), characters[1], scale=1.0)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out
