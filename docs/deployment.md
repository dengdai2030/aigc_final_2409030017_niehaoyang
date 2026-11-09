# 部署指南

> 第 14 周提交物 · `docs/deployment.md`

## 1. 环境依赖（含版本号）

| 依赖 | 版本 | 必需性 |
| --- | --- | --- |
| 操作系统 | Windows 10/11、macOS 12+、Linux（任一） | 必需 |
| Python | ≥ 3.10（开发验证于 3.13） | 必需 |
| Pillow | ≥ 10 | 必需（插画/绘本） |
| edge-tts | ≥ 7 | 推荐（有声书真语音，需联网） |
| imageio-ffmpeg | ≥ 0.5 | 必需（自带 ffmpeg 静态二进制，**无需单独安装 ffmpeg**） |
| openai / requests | ≥ 1.0 / ≥ 2.3 | 可选（仅在线 LLM 模式） |

## 2. 配置说明

复制 `.env.example` 为 `.env`，按需修改：

| 变量 | 取值 | 说明 |
| --- | --- | --- |
| LLM_PROVIDER | `mock`（默认）/ `openai` | 离线模板创作器 / 在线 OpenAI 兼容接口 |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | - | 在线模式必填；密钥只存 .env，已被 .gitignore 排除 |
| IMAGE_PROVIDER | `local`（默认）/ `dashscope` | 本地程序化插画 / 通义万相 |
| TTS_PROVIDER | `edge`（默认）/ `off` | Edge TTS（免费需联网）/ 静音降级 |

> **零配置可跑**：不创建 `.env` 时全部走离线降级（mock + local + edge），除 TTS 外无任何外部服务依赖。

## 3. 部署步骤

```bash
# 1. 获取代码
git clone <仓库地址> && cd aigc_final_学号_姓名拼音
# （或解压源码包后进入目录）

# 2. （推荐）创建虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. （可选）配置在线增强
cp .env.example .env          # 编辑填入密钥

# 5. 启动 Web 服务
python scripts/run_server.py 8000
# 浏览器打开 http://127.0.0.1:8000
```

## 4. 部署验证方法

1. 打开 `http://127.0.0.1:8000`，页面标题"故事精灵 StorySprout"正常显示（截图 `deployment_screenshots/01_首页.png`）；
2. 点"✨ 让 Agent 开始创作"，等待 6 步全部变绿（约 1-3 分钟），产物区出现插画、音频播放器、视频播放器与"📕 绘本 PDF"链接（截图 `02_创作产物页.png`）；
3. 访问 `http://127.0.0.1:8000/api/state` 返回 JSON 且 `"busy": false`（截图 `03_运行验证_接口状态.png`）；
4. 命令行验证测试套件：`python -m unittest discover -s tests`，应输出 `OK`（43 例）；
5. 命令行验证端到端：`python -m storysprout.cli "森林冒险" --tag verify`，返回 JSON 中 `"ok": true`。

以上 5 项全部通过即部署成功（实测截图见 `deployment_screenshots/`）。

## 5. 常见问题（FAQ）

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 有声书时长明显偏短、听不到人声 | edge-tts 断网/被限流，单句降级为静音 | 检查网络后重跑；或接受降级（字幕仍同步） |
| `ModuleNotFoundError: storysprout` | 用 `python -m storysprout.server` 直接启动 | 请用 `python scripts/run_server.py`（已注入 src 路径） |
| 端口被占用 | 8000 被占 | `python scripts/run_server.py 8080` 换端口 |
| 插画风格朴素 | 当前为本地程序化插画（IMAGE_PROVIDER=local） | 配置通义万相密钥切在线文生图 |
| 首次创作慢 | TTS 逐句合成占大头（约 3 秒/句） | 正常现象；干预改名不会重画图，显著快于全量 |
| ffmpeg 相关报错 | imageio-ffmpeg 未装全 | `pip install -r requirements.txt` 重装 |
