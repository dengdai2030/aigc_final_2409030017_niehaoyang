# 中期进度报告

> 第 12 周提交物 · `docs/midterm_report.md`

## 1. 功能完成度表（对照提案 F1–F9）

| # | 功能 | 计划优先级 | 状态 | 验证证据 |
| --- | --- | --- | --- | --- |
| F1 | 创意→多模态产品（6 工具链） | P0 | ✅ 完成 | 原型端到端 173.9s，产物齐全（`outputs/` 下 story/json、png×6、mp3 148s、mp4、pdf 8页） |
| F2 | 创作中途干预（最小重算） | P0 | ✅ 完成 | Web 实测：「把主角改成朵拉」→ 只重跑 voice(78.5s)/compose_video(5.4s)/build_book(0.2s)，插画复用，产物独立命名 `web_干预后_*` |
| F3 | 全程可观测（trace/日志导出） | P0 | ✅ 完成 | `outputs/traces/trace_web.json` + `log_web.md`，UI 实时显示每步状态/耗时 |
| F4 | API 可靠性（重试/缓存/降级） | P0 | ✅ 完成 | LLM 3 次指数退避；响应落盘缓存；TTS 单句重试+单句降级+断网兜底（见 §3 Bug-T1） |
| F5 | 成本计量 | P1 | ✅ 完成 | `GLOBAL_USAGE` 全局计量，UI 显示"本次成本"（mock 模式 ¥0；在线按 token 估算） |
| F6 | 素材检索推荐 | P1 | ✅ 完成 | 10 模板库 + 字符 n-gram 打分，检索结果注入写作 Prompt |
| F7 | 多角色有声书 | P1 | ✅ 完成 | 3 音色（旁白/主角/伙伴）+ 6 档情绪参数 + 程序化 BGM，27 句 148 秒 |
| F8 | 字幕短视频 | P2 | ✅ 完成 | 时间轴驱动逐句烧字幕，音画同步 |
| F9 | Web 界面（零依赖） | P0 | ✅ 完成 | 标准库 http.server + 单页 UI，API 实测通过（create/state/intervene） |

**总体进度：P0/P1 功能全部完成，P2 完成。进度符合提案计划，略超前。**

## 2. 当前架构图

```
Web UI (web/index.html)  ──HTTP──▶  server.py（标准库，线程化）
                                      │
                            agent.py  StoryAgent
                     规划器 Rule/LLM │ 干预：FIELD_IMPACT 最小重算
                                      ▼
                 tools.py 注册表 ── search_materials / write_story / illustrate
                                   / voice / compose_video / build_book
                                      ▼
    composer(离线写作) llm(在线+缓存) illustration(PIL) tts(edge-tts)
    video(ffmpeg) book(PDF) templates.json(素材库)
```

与提案 §3.1 的差异：`cost.py` 并入 `llm.py` 的 `Usage/GLOBAL_USAGE`（更内聚）；新增 `composer.py`（技术验证后从 llm.py 拆出的独立降级模块）。

## 3. 已解决的技术问题（含 Bug 记录）

| 编号 | 问题 | 根因 | 修复 | 验证 |
| --- | --- | --- | --- | --- |
| Bug-T1 | edge-tts 偶发 "No audio was received"，首轮运行整本有声书静音 | 原实现单句失败即全局切换离线；停顿句用 `-100%` 语速调 API（必然失败） | ① 每句重试 2 次；② 单句失败只降级该句（静音占位+估算时长）；③ 连续 3 句失败才判离线；④ 停顿改本地静音 WAV | 复测 27/27 句合成，148.02s |
| Bug-T2 | 干预后 compose_video 失败（PermissionError: '.'） | 干预路径绕过 `_resolve_args`，`timeline_file=""` → `Path("").read_text` | 干预循环内补时间轴解析：总是取最新 voice 产物 | Web 复测干预后短片 5.4s 生成 |
| Bug-T3 | 演示视频脚本帧图丢失 | `build()` 开头误清空已生成的帧 | 移除清理循环 | 两支演示视频生成成功 |

## 4. 未解决的技术问题

| 问题 | 影响 | 计划 |
| --- | --- | --- |
| 在线 LLM / 在线文生图路径未实测（本机无密钥） | 答辩现场若用在线模式属首次运行 | 第 13 周配置密钥补测；离线降级已保证演示底线 |
| UI 截图未采集 | 第 14 周部署验证材料 | 第 14 周部署时统一截图 |
| 模板创作器长创意下偶有句式重复 | 仅影响降级模式文风 | 第 13 周测试评估是否扩变体库 |

## 5. 核心代码片段说明

**干预最小重算（`agent.py` + `tools.py`）**——本项目的核心难点：

```python
# tools.py：变更字段 → 受影响工具（改名不重画图）
FIELD_IMPACT = {
    "protagonist": ["voice", "compose_video", "build_book"],
    "age": ["write_story", "illustrate", "voice", "compose_video", "build_book"], ...
}

# agent.py：干预 → 解析 → 只重跑受影响步骤
after, changed = self._parse(instruction, before)
affected = self._affected(...)          # [voice, compose_video, build_book]
if "protagonist" in changed:            # 确定性改名：全文替换写副本
    dst.write_text(src.read_text().replace(old, new))
for tool_name in affected:
    self._exec(Step(99, tool_name, args))
```

**TTS 可靠性（`tts.py`）**：单句级重试与降级，任何一句失败不影响整本：

```python
for attempt in range(2):
    try:
        dur = _synth_once(...); consecutive_fail = 0; break
    except Exception:
        logger.warning("句子 %d 第 %d 次合成失败", idx + 1, attempt + 1)
else:
    consecutive_fail += 1
if dur == 0.0:
    dur = _estimate_dur(sent); _silence_wav(wav, dur)   # 该句降级，全局不污染
```

## 6. 运行环境说明

- Windows 11 · Python 3.13 · 无 LLM 密钥（LLM_PROVIDER=mock）· IMAGE_PROVIDER=local · TTS_PROVIDER=edge（联网）
- 依赖：`requirements.txt`（Pillow / edge-tts / imageio-ffmpeg / openai / requests，后两者仅在线模式用）
- 启动：`python scripts/run_server.py 8000` → http://127.0.0.1:8000
- 命令行：`python -m storysprout.cli "创意" --intervene "把主角改成朵拉"`
- 测试：`python -m unittest discover -s tests`（第 13 周交付）

## 7. 第 13–15 周计划

| 周 | 计划 |
| --- | --- |
| 第 13 周 | 单元测试（schema/干预解析/JSON 修复/插画确定性/TTS 时长估算）≥20 例；功能/Prompt/异常测试用例文档；在线模式补测；根据测试迭代修复 |
| 第 14 周 | 部署指南 + 用户手册 + API 文档 + 架构终稿 + 部署验证截图（Web UI 实拍） |
| 第 15 周 | 完整仓库整理 + reflection.md + AI 日志终稿 + 8-12 分钟演示视频 + 现场答辩演练 |

演示视频说明：`outputs/video/midterm_demo.mp4`（94 秒）与 `prototype_demo.mp4`（45 秒）为程序从真实运行产物合成的配音讲解视频；按课程要求，第 15 周将另录 8-12 分钟含本人配音的屏幕操作演示。
