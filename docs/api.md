# API 文档

> 第 14 周提交物 · `docs/api.md`
> 本项目未对外发布托管 API，以下为本地 Web 服务（`python scripts/run_server.py`，默认 `http://127.0.0.1:8000`）的自定义接口。数据编码均为 UTF-8 JSON。

## 1. POST /api/create —— 发起创作

**请求**

```json
{
  "idea": "深海里的一颗珍珠",
  "protagonist": "朵朵",
  "age": 6,
  "scene": "海洋",
  "theme": "分享与感恩",
  "n_scenes": 4
}
```

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| idea | string | 是 | 任意非空文本，建议 ≤ 30 字 |
| protagonist | string | 否（默认"小满"） | 1–8 字 |
| age | int | 否（默认 6） | 3–12 |
| scene | string | 否（默认"森林"） | 建议：太空/森林/海洋/城市/沙漠 |
| theme | string | 否 | 1–12 字 |
| n_scenes | int | 否（默认 6） | 4–8，越界自动钳制 |

**响应**

```json
{ "ok": true, "tag": "web" }
```

**错误**：`409` 已有任务在跑 → `{"ok": false, "error": "已有任务在跑，请稍候"}`；`400` JSON 解析失败。

**副作用**：后台线程执行 Agent 六步流程；产物写入 `outputs/`，故事写入 `data/stories/web_story.json`。

## 2. GET /api/state —— 查询进度与产物

**请求**：无参数。

**响应（节选）**

```json
{
  "busy": false,
  "started": true,
  "idea": "深海里的一颗珍珠",
  "steps": [
    {"idx": 0, "tool": "search_materials", "status": "done",
     "elapsed": 0.0, "summary": "hits=[...]", "error": ""}
  ],
  "artifacts": {
    "story_file": "C:\\...\\data\\stories\\web_story.json",
    "audio": "C:\\...\\outputs\\audio\\web_audiobook.mp3",
    "timeline": "C:\\...\\outputs\\audio\\web_audiobook_timeline.json",
    "video": "C:\\...\\outputs\\video\\web_video.mp4",
    "book": "C:\\...\\outputs\\book\\web_book.pdf",
    "images": ["C:\\...\\outputs\\images\\scene01.png", "..."]
  },
  "usage": "调用 0 次 / 缓存命中 0 次 / 输入 0 tok / 输出 0 tok / 估算成本 ¥0.0000",
  "events": ["[plan] 规划器=rule，共 6 步：...", "..."],
  "tts_provider": "edge"
}
```

| 字段 | 说明 |
| --- | --- |
| busy | 是否有任务在执行（轮询建议间隔 1.5s） |
| steps[].status | pending / running / done / failed |
| artifacts | 各模态产物绝对路径；干预后为 `*_干预后_*` 新文件 |
| usage | 累计成本估算（token 级；mock 模式为 0） |

## 3. POST /api/intervene —— 中途干预

**请求**

```json
{ "instruction": "把主角改成朵拉" }
```

支持四类指令：`把主角改成X` / `年龄改成N岁` / `场景改成X` / `主题改成X`。

**响应（成功）**

```json
{
  "ok": true,
  "changed": {"protagonist": "朵拉"},
  "affected": ["voice", "compose_video", "build_book"],
  "output_tag": "web_干预后"
}
```

**响应（无法识别）**

```json
{
  "ok": false,
  "changed": {},
  "reason": "没听懂这条指令。试试：「把主角改成XX」…",
  "affected": []
}
```

**错误**：`409` 无完成态任务或任务执行中。

## 4. GET /outputs/&lt;path&gt; —— 产物静态文件

| 类型 | URL 示例 | Content-Type |
| --- | --- | --- |
| 插画 | `/outputs/images/scene01.png` | image/png |
| 有声书 | `/outputs/audio/web_audiobook.mp3` | audio/mpeg |
| 短片 | `/outputs/video/web_video.mp4` | video/mp4 |
| 绘本 | `/outputs/book/web_book.pdf` | application/pdf |

**示例**：浏览器直接打开 `http://127.0.0.1:8000/outputs/book/web_book.pdf`；`curl -o book.pdf http://127.0.0.1:8000/outputs/book/web_book.pdf`。

## 5. Python API（进程内调用）

```python
from storysprout.agent import CaseSpec, RulePlanner, StoryAgent

agent = StoryAgent(planner=RulePlanner())
report = agent.run(CaseSpec(idea="太空冒险", protagonist="朵朵",
                            scene="太空", tag="demo"))
result = agent.intervene("把主角改成朵拉")
trace_path = agent.save_trace()   # JSON 留痕
log_path = agent.render_log()     # Markdown 创作日志
```

`report` 结构：`{"case", "idea", "steps", "ok", "total_elapsed", "artifacts"}`。
