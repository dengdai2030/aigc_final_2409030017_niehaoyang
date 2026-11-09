"""生成演示视频（prototype_demo.mp4 / midterm_demo.mp4）。

形式：讲解配音 + 画面（标题卡 / 进度卡 / 真实产物图 / 干预对比）。
说明：本视频由程序从真实运行产物合成，非屏幕录制；
课堂如需"现场操作录屏"，可自行录屏替换，脚本不影响评分材料链。
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from storysprout.config import AUDIO_DIR, IMAGE_DIR, OUTPUT_DIR, VIDEO_DIR  # noqa: E402

W, H = 1280, 720
SEG_DIR = VIDEO_DIR / "_clips"


def _font(size, bold=False):
    from PIL import ImageFont
    for name in (("msyhbd.ttc", "msyh.ttc") if bold else ("msyh.ttc", "simsun.ttc")):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _card(title, lines, out, accent=(232, 131, 58)):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (250, 246, 239))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=accent)
    f1, f2 = _font(52, True), _font(30)
    y = 150
    tw = d.textlength(title, font=f1)
    d.text(((W - tw) / 2, y), title, font=f1, fill=(58, 50, 48))
    y += 110
    for ln in lines:
        tw = d.textlength(ln, font=f2)
        d.text(((W - tw) / 2, y), ln, font=f2, fill=(120, 105, 95))
        y += 54
    img.save(out, "JPEG", quality=90)


def _photo(src, caption, out):
    from PIL import Image, ImageDraw
    img = Image.open(src).convert("RGB").resize((W, H))
    d = ImageDraw.Draw(img, "RGBA")
    f = _font(30)
    d.rounded_rectangle([60, H - 92, W - 60, H - 34], radius=14, fill=(20, 18, 28, 175))
    tw = d.textlength(caption, font=f)
    d.text(((W - tw) / 2, H - 84), caption, font=f, fill=(255, 250, 240))
    img.save(out, "JPEG", quality=90)


def _grid(paths, caption, out):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (250, 246, 239))
    d = ImageDraw.Draw(img)
    cw, ch = 560, 315
    pos = [(80, 90), (660, 90), (80, 430 - 40), (660, 430 - 40)]
    for p, (x, y) in zip(paths, pos):
        img.paste(Image.open(p).convert("RGB").resize((cw, ch)), (x, y))
    f = _font(28)
    d.rounded_rectangle([60, H - 92, W - 60, H - 34], radius=14, fill=(20, 18, 28, 175))
    tw = d.textlength(caption, font=f)
    d.text(((W - tw) / 2, H - 84), caption, font=f, fill=(255, 250, 240))
    img.save(out, "JPEG", quality=90)


def _tts(text, wav_path: Path) -> float:
    import asyncio
    import edge_tts
    mp3 = wav_path.with_suffix(".mp3")
    asyncio.run(edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural", rate="+6%").save(str(mp3)))
    ff = _ffmpeg()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "22050", "-ac", "1",
                    str(wav_path)], check=True, capture_output=True)
    with wave.open(str(wav_path), "rb") as f:
        return round(f.getnframes() / f.getframerate(), 3)


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def build(segments, out_name: str) -> Path:
    SEG_DIR.mkdir(parents=True, exist_ok=True)
    wavs, list_txt = [], SEG_DIR / "list.txt"
    with open(list_txt, "w", encoding="utf-8") as f:
        for i, (img, text) in enumerate(segments):
            wav = SEG_DIR / f"n{i:02d}.wav"
            dur = _tts(text, wav) + 0.9
            wavs.append(dur)
            f.write(f"file '{Path(img).as_posix()}'\nduration {dur:.3f}\n")
        f.write(f"file '{Path(segments[0][0]).as_posix()}'\n")
    audio_list = SEG_DIR / "alist.txt"
    with open(audio_list, "w", encoding="utf-8") as f:
        for i in range(len(segments)):
            f.write(f"file '{(SEG_DIR / f'n{i:02d}.wav').as_posix()}'\n")
            pause = SEG_DIR / "_p.wav"
            if not pause.exists():
                import struct
                with wave.open(str(pause), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
                    w.writeframes(b"\x00\x00" * int(22050 * 0.9))
            f.write(f"file '{pause.as_posix()}'\n")

    silent = SEG_DIR / "video_only.mp4"
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(list_txt), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "24", str(silent)], check=True, capture_output=True)
    narr = SEG_DIR / "narr.wav"
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(audio_list), "-ar", "22050", str(narr)],
                   check=True, capture_output=True)
    out = VIDEO_DIR / out_name
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(silent), "-i", str(narr),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True, capture_output=True)
    print("生成:", out, f"{sum(wavs):.0f}s")
    return out


def build_proto() -> None:
    """第11周原型演示（2-3分钟）：聚焦端到端流程。"""
    img = IMAGE_DIR
    seg_frames = SEG_DIR
    seg_frames.mkdir(parents=True, exist_ok=True)

    f0 = seg_frames / "p_t.jpg"; _card("技术验证 · 端到端原型",
        ["一条命令跑通：创意 → 四种模态", "python src/prototype/run_prototype.py",
         "第 11 周 · 技术验证"], f0)
    f1 = seg_frames / "p_1.jpg"; _photo(img / "scene01.png", "验证一：Agent 六步全通，端到端 173.9 秒", f1)
    f2 = seg_frames / "p_2.jpg"; _photo(img / "scene05.png", "验证二：固定 seed + 特征卡，角色跨场景一致", f2)
    f3 = seg_frames / "p_3.jpg"; _card("验证三：可靠性与确定性",
        ["27/27 句 TTS 合成成功 · 148 秒有声书", "模板创作器同输入逐字节一致",
         "schema 通过率 5/5"], f3)

    segs = [
        (f0, "这是故事精灵的技术验证演示。目标是验证一条命令能否把一句创意，跑成绘本、有声书和短片三种产物。"),
        (f1, "运行端到端原型脚本，创作代理依次完成检索、写作、配图、配音、合成和排版六个步骤，全部成功，总耗时约三分钟。"),
        (f2, "配图采用固定种子加角色特征卡的方案，主角朵朵和光团伙伴在每一个场景里形象保持一致。"),
        (f3, "可靠性方面，二十七句语音全部合成成功，离线创作器输出完全确定，五组创意全部通过数据校验。六项技术验证全部采纳。"),
    ]
    build(segs, "prototype_demo.mp4")


def main() -> None:
    img = IMAGE_DIR
    seg_frames = SEG_DIR
    seg_frames.mkdir(parents=True, exist_ok=True)

    f00 = seg_frames / "f_t.jpg";  _card("故事精灵 StorySprout",
        ["交互式多模态故事创作 Agent", "创意 → 绘本 + 有声书 + 短视频", "后半学期大项目 · 中期演示"], f00)
    f01 = seg_frames / "f_s.jpg";  _card("Agent 自主规划 6 步",
        ["search_materials → write_story → illustrate", "→ voice → compose_video → build_book",
         "每步耗时 / 状态 / 产物 全程可观测"], f01)
    f02 = seg_frames / "f_i.jpg";  _photo(img / "scene01.png", "① 写作 + 配图：主角朵朵与光团伙伴（固定 seed 保角色一致）", f02)
    f03 = seg_frames / "f_i2.jpg"; _photo(img / "scene03.png", "② 多角色配音：旁白 / 朵朵 / 布布 三音色，句级时间轴", f03)
    f04 = seg_frames / "f_i3.jpg"; _photo(img / "scene04.png", "③ 短片与绘本：同一份故事数据驱动全部模态", f04)
    f05 = seg_frames / "f_iv.jpg"; _card("用户中途干预",
        ["「把主角改成朵拉」", "变更解析 → 依赖图计算最小重算集", "只重跑 voice / 短片 / 绘本，插画直接复用"], f05)
    f06 = seg_frames / "f_g.jpg";  _grid([img / "scene01.png", img / "scene02.png",
                                          img / "scene03.png", img / "scene04.png"],
                                         "④ 产物总览：故事 JSON · 插画 · 有声书 MP3 · 短片 MP4 · 绘本 PDF", f06)
    f07 = seg_frames / "f_e.jpg";  _card("工程可靠性",
        ["API 重试 + 指数退避 · 响应缓存 · 成本计量", "无密钥 / 断网 自动降级，演示永不停摆",
         "谢谢观看 · 现场演示见答辩环节"], f07)

    segs = [
        (f00, "大家好，这里是故事精灵。用户只需要输入一句创意，它就能自动产出一套完整的多模态儿童故事产品。"),
        (f01, "收到创意后，创作代理会先做检索，再自主规划成六步：检索素材、写作、配图、配音、合成短片、排版绘本，每一步的耗时和产物都实时可见。"),
        (f02, "写作模块输出结构化的故事数据，配图模块用固定的随机种子和角色特征卡，保证主角在每一个场景里都是同一个形象。"),
        (f03, "配音模块为旁白和不同角色分配不同音色，并根据每一幕的情绪调整语速和音调，同时生成逐句的时间轴。"),
        (f04, "短片和绘本都由同一份故事数据驱动：画面、配音、字幕按时间轴对齐，绘本则排版成封面、图文页和寓意页。"),
        (f05, "最有意思的是中途干预。用户说：把主角改成朵拉。系统解析变更后，只重跑配音、短片和绘本三步，已经画好的插画直接复用，又快又省钱。"),
        (f06, "最终产物包括结构化故事、插画、有声书、短片和绘本，四种模态全部来自同一个数据源。"),
        (f07, "工程上，项目内置了重试、缓存、成本计量和三级降级，没有密钥或者断网也能完整演示。谢谢观看。"),
    ]
    build(segs, "midterm_demo.mp4")


if __name__ == "__main__":
    if "--proto" in sys.argv:
        build_proto()
    else:
        main()
