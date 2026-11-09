"""故事精灵 StorySprout · 交互式多模态故事创作 Agent。

后半学期大项目（题目库 #2）。模块一览：

- config        全局配置：路径、.env 加载、三级降级开关
- schema        故事数据结构（Story/Character/Scene）与校验
- prompts       Prompt 模板（版本化）
- composer      离线模板创作器（LLM 降级方案，确定性输出）
- llm           OpenAI 兼容客户端：重试 / 缓存 / JSON 修复 / 成本计量
- illustration  插画：在线文生图 / 本地 PIL 程序化插画（固定 seed 保角色一致）
- tts           多角色配音（edge-tts）+ 句级时间轴
- video         图片+音频+字幕 → 短片（ffmpeg，来自 imageio-ffmpeg）
- book          绘本排版（PIL → 多页 PDF）
- tools         工具注册表（Agent 的"手"）
- agent         Agent 循环：规划 → 执行 → 干预重算（Agent 的"脑"）
- server        零依赖本地 Web 服务
"""

__version__ = "0.3.0"
