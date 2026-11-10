# 故事精灵 StorySprout · 多模态故事创作 Agent

> AIGC 应用开发实践 · 后半学期大项目（题目库 #2：多模态故事Agent）
> 作者：聂浩洋（学号：2409030017）　|　单人项目

**一句话**：用户输入一句故事创意，Agent 自主规划并调用 6 类工具，产出 **绘本 + 有声书 + 短视频 + 结构化故事文稿** 四种模态的完整产品；创作中途可随时干预（"把主角改成朵拉"），系统自动计算最小重算集，只重跑受影响的步骤。

---

## 快速启动

```bash
pip install -r requirements.txt
python scripts/run_server.py 8000     # 打开 http://127.0.0.1:8000
```

命令行方式：

```bash
python -m storysprout.cli "太空冒险" --protagonist 朵朵 --scene 太空 \
       --intervene "把主角改成朵拉"
```

跑测试：

```bash
python -m unittest discover -s tests     # 43 例，输出 OK
```

> 零配置可跑：不配任何密钥时自动进入离线降级模式（模板创作器 + 本地插画 + Edge TTS）。

## 功能特性

- 🤖 **Agent 循环**：规划 → 工具执行 → 观测 → 干预重算，全程 trace 留痕
- 🎛️ **中途干预**：改名/改年龄/改场景/改主题，依赖图计算最小重算集（改名不重画图）
- 📚 **四种模态**：故事 JSON / 逐场景插画 / 多角色有声书（句级时间轴）/ 带字幕短片 / PDF 绘本
- 🎨 **角色一致性**：全局固定 seed + 角色特征卡，跨场景形象一致
- 🔊 **多角色配音**：3 音色 × 6 档情绪参数 + 程序化八音盒 BGM
- 🛡️ **工程可靠性**：API 重试+指数退避、响应缓存、成本计量、三级降级（在线→缓存→离线）
- 🖥️ **零依赖 Web UI**：标准库 http.server，进度/事件/成本实时可见

## 技术栈

Python 3.10+ · Pillow（插画/PDF）· edge-tts（语音）· imageio-ffmpeg（视频，免装 ffmpeg）· openai SDK（在线模式，可选）· unittest

## AI 协作说明

本项目在大模型（WorkBuddy/GLM）深度辅助下完成，所有 AI 生成内容经过本人运行验证与修改。工具调用记录、人工修改明细与生成占比估算见 [`ai_log.md`](ai_log.md)；个人反思见 [`reflection.md`](reflection.md)。

## 文档导航

| 内容 | 位置 |
| --- | --- |
| 第9周 选题意向表 | `docs/week9_选题意向表.md` |
| 第10周 课程设计提案 | `docs/proposal.md`（tag v1-proposal） |
| 第11周 技术验证报告 | `docs/tech_validation.md` |
| 第12周 中期进度报告 | `docs/midterm_report.md`（tag v2-midterm） |
| 第13周 测试用例 / 测试报告 | `docs/test_cases.md` / `docs/test_report.md` |
| 第14周 部署指南 / 用户手册 / API / 架构终稿 | `docs/deployment.md` / `user_manual.md` / `api.md` / `architecture_final.md` |
| 部署验证截图 | `docs/deployment_screenshots/` |
| 创作流程日志 | `outputs/traces/` |

## 仓库标签

`v1-proposal`（第10周提案）→ `v2-midterm`（第12周MVP）→ `v3-final`（第15周最终版）
