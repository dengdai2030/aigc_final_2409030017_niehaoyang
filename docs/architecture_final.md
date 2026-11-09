# 架构终稿

> 第 14 周提交物 · `docs/architecture_final.md`
> 与中期版本（`midterm_report.md` §2）的差异用 ⭐ 标注。

## 1. 系统架构图（最终版）

```
┌──────────────────────── Web UI（web/index.html，单页零构建）────────────────────────┐
│  表单(创意/主角/世界/主题/场景数) │ 步骤进度条 │ 事件流 │ 干预框+快捷指令 │ 产物预览  │
└──────────────▲─────────────────────────────────────────────────┬──────────────────┘
               │ GET /api/state (1.5s轮询) / 静态 /outputs/*      │ POST /api/create
               │                                                 │ POST /api/intervene
┌──────────────┴─────────────────────────────────────────────────▼──────────────────┐
│                     server.py（标准库 ThreadingHTTPServer，零第三方依赖）            │
│                     ⭐ 全局 LOCK 串行化任务状态；后台线程执行创作                    │
├───────────────────────────────────────────────────────────────────────────────────┤
│                       agent.py —— StoryAgent（Agent 循环）                         │
│                                                                                   │
│   observe(创意) → plan → act(工具) → observe → … → report                          │
│                     │                   ↑                                         │
│        规划器可插拔：│                   │ intervene(instruction)                   │
│        RulePlanner ─┤ 离线固定DAG       │ 变更解析→FIELD_IMPACT最小重算→下游重跑     │
│        LLMPlanner ──┘ 在线拆步骤(失败回退)│ 改名=确定性全文替换写副本，插画复用        │
│                                                                                   │
│   全程留痕：trace(JSON) + render_log(Markdown) ⭐ 落盘 outputs/traces/              │
├───────────────────────────────────────────────────────────────────────────────────┤
│  tools.py —— 工具注册表（name / description / params / fn / produces）              │
│    search_materials ─► data/templates.json（10 模板，字符 n-gram 打分）             │
│    write_story ──────► llm.py（在线：重试/缓存/JSON修复/成本计量）                   │
│                          └► composer.py（⭐ 独立降级模块：六幕弧+世界意象库，确定性）  │
│    illustrate ───────► illustration.py（⭐ 最终：本地 PIL，seed+特征卡一致性；        │
│                          dashscope 在线路径已封装于配置层，密钥就绪即启用）           │
│    voice ────────────► tts.py（edge-tts 逐句：3音色×6情绪档；                        │
│                          可靠性：单句重试2次→单句降级→连续3句失败才判离线；           │
│                          本地静音WAV停顿；句级 timeline.json）                       │
│    compose_video ────► video.py（timeline 驱动逐句帧 + PIL 烧字幕 +                  │
│                          imageio-ffmpeg concat 合成，音画同源）                     │
│    build_book ───────► book.py（PIL 排版：封面+图文页+寓意页 → 多页 PDF）            │
├───────────────────────────────────────────────────────────────────────────────────┤
│  schema.py（Story/Character/Scene 逐字段校验）   config.py（.env/三级降级开关）      │
│  ⭐ tests/（43 例单测）  ⭐ scripts/（run_server / make_demo_video）                 │
└───────────────────────────────────────────────────────────────────────────────────┘
```

## 2. 关键架构决策（最终确认）

| 决策 | 选择 | 理由（答辩口径） |
| --- | --- | --- |
| Agent 框架 | 自研轻量循环 + 可插拔规划器，附 LangChain 迁移路径 | 工具表 schema 与 LangChain Tool 定义同构；教学场景下 300 行自研代码比黑盒框架更可讲、可测 |
| 模态间一致性 | 单一数据源（story.json + timeline.json）驱动四模态 | 干预最小重算建立在"依赖显式化"之上 |
| 降级链 | mock/local/off 三级，逐句粒度劣化 | 演示永不停摆；Bug-T1 证明其价值 |
| 视频字幕 | PIL 烧录而非 ffmpeg drawtext | 规避中文转义与字体问题；字幕样式与绘本一致 |
| Web 服务 | 标准库 http.server | 零部署依赖，双击可跑；接口已按 REST 语义组织，可平移 FastAPI |
| ffmpeg 获取 | imageio-ffmpeg 自带静态二进制 | 免安装 ffmpeg，部署成本最低 |

## 3. 数据流（最终版）

1. **创作**：`POST /api/create` → 线程启动 → search（模板命中注入 Prompt）→ write（在线 LLM 或 composer）→ story.json（schema 校验）→ illustrate（seed+特征卡 → sceneNN.png）→ voice（逐句合成 → mp3 + timeline.json）→ compose_video（timeline → 帧字幕 → mp4）→ build_book（→ pdf）
2. **干预**：`POST /api/intervene` → 正则解析变更字段 → `FIELD_IMPACT` 映射受影响工具 → 改名走确定性全文替换（副本 `*_干预后.json`）→ 顺序重跑受影响工具 → 新产物 `web_干预后_*`，原产物保留
3. **观测**：前端 1.5s 轮询 `/api/state`；trace 同步落盘，答辩可展示完整决策链

## 4. 目录结构（最终版）

```
aigc_final_学号_姓名拼音/
├── README.md                  ⭐ 最终版（第15周补全）
├── requirements.txt  .env.example  .gitignore
├── ai_log.md                  ⭐ 第9-15周AI协作日志
├── reflection.md              ⭐ 第15周
├── src/
│   ├── storysprout/           # 主包（12 个模块）
│   │   ├── agent.py  tools.py  server.py  web/index.html
│   │   ├── schema.py  composer.py  llm.py  prompts.py
│   │   ├── illustration.py  tts.py  video.py  book.py
│   │   └── config.py  cli.py
│   └── prototype/run_prototype.py   # 第11周原型（保留可跑）
├── tests/                     # 43 例单元测试
├── scripts/                   # run_server.py / make_demo_video.py
├── data/                      # templates.json / stories/
├── outputs/                   # audio / video / book / images / traces
├── docs/                      # 第9-14周全部文档 + deployment_screenshots/
└── logs/  .cache/             # 运行时（gitignore）
```

## 5. 质量基线（截至第 14 周）

- 单元测试：43/43 通过（`python -m unittest discover -s tests`）
- 端到端：原型 173.9s 全绿；Web 创作+干预实测通过（见中期报告 §1）
- 角色一致性：seed+特征卡方案，跨场景肉眼一致
- 可靠性：4 个已修复 Bug 均有回归覆盖（Bug-T1～T4）
