# 测试用例文档

> 第 13 周提交物 · `docs/test_cases.md`
> 测试代码：`tests/`（`python -m unittest discover -s tests` 可自动执行）

## 1. 功能测试用例（每核心功能 ≥2 例）

### F1 创意→多模态产品（写故事）

| 编号 | 用例 | 输入 | 预期 | 对应测试 |
| --- | --- | --- | --- | --- |
| TC-F1-1 | 标准创意生成 | idea="太空冒险", scene=太空 | 返回 Story，6 场景，schema 通过 | `test_composer.TestComposer.test_schema_pass_various_ideas` |
| TC-F1-2 | 主角名注入 | protagonist=朵拉 | hero.name=朵拉 且正文含"朵拉" | `test_protagonist_used` |
| TC-F1-3 | 场景数钳制 | n_scenes=99 | 场景数 ≤ 6 | `test_scene_count_clamped` |
| TC-F1-4 | 情绪弧完整 | n_scenes=6 | mood 序列 = 好奇/期待/挑战/低谷/转机/圆满 | `test_mood_arc_covers_six_beats` |

### F2 创作中途干预

| 编号 | 用例 | 输入 | 预期 | 对应测试 |
| --- | --- | --- | --- | --- |
| TC-F2-1 | 改主角名 | "把主角改成朵拉" | changed={protagonist:朵拉}，重算集=voice/短片/绘本 | `test_agent.TestInterveneParse.test_rename` |
| TC-F2-2 | 带引号改名 | "主角改成“小树”" | 正确解析出 小树 | `test_rename_with_quotes` |
| TC-F2-3 | 改年龄（类型） | "年龄改成7岁" | age=7 且为 int | `test_age` |
| TC-F2-4 | 无法识别 | "今天天气不错" | changed={}，不触发重算 | `test_unrecognized_instruction` |
| TC-F2-5 | 无变化指令 | "主角改成朵朵"（同名） | changed={} | `test_no_change_when_same` |
| TC-F2-6 | 重算集去重 | 同时改场景+年龄 | 受影响工具无重复 | `TestMinimalRecompute` |

### F4 Prompt / 结构化输出

| 编号 | 用例 | 输入 | 预期 | 对应测试 |
| --- | --- | --- | --- | --- |
| TC-F4-1 | 纯 JSON 解析 | `{"a":1}` | 解析成功 | `test_llm.test_plain_json` |
| TC-F4-2 | Markdown 围栏 | \```json...\``` | 剥壳解析 | `test_markdown_fence` |
| TC-F4-3 | 前后废话包裹 | "好的：{...}完毕" | 括号配平提取 | `test_prose_wrapped` |
| TC-F4-4 | 尾逗号 | `{"a":[1,2,],}` | 修复后解析 | `test_trailing_comma` |
| TC-F4-5 | 全角引号 | `{"a“：“b”}` | 归一化后解析 | `test_fullwidth_quotes` |
| TC-F4-6 | 字符串含花括号 | `{"s":"包含 } 的字符串"}` | 不被括号配平破坏 | `test_nested_braces_in_strings` |
| TC-F4-7 | 彻底非法 | "这不是JSON" | 抛 ValueError | `test_garbage_raises` |

## 2. 异常测试用例

| 编号 | 用例 | 输入 | 预期 | 对应测试 |
| --- | --- | --- | --- | --- |
| TC-E-1 | 缺顶层字段 | 删掉 moral 的故事 dict | StorySchemaError 指明缺失字段 | `test_schema.test_missing_top_field` |
| TC-E-2 | scene_id 重复 | 两场景同 id | StorySchemaError | `test_duplicate_scene_id` |
| TC-E-3 | 正文过短 | text="太短了" | StorySchemaError | `test_short_scene_text_rejected` |
| TC-E-4 | scene_id 非整数 | "abc" | StorySchemaError | `test_scene_id_must_be_int` |
| TC-E-5 | 角色缺字段 | traits 为空 | StorySchemaError | `test_character_missing_field` |
| TC-E-6 | TTS 断网降级 | 合成失败 | 该句静音占位+估算时长，整本不崩 | 第 12 周实测（Bug-T1 修复回归） |
| TC-E-7 | 干预时序错误 | 未创作先干预 | 返回拒绝原因，不崩溃 | Web 实测（HTTP 409 / reject 事件） |

## 3. 确定性 / 回归测试用例

| 编号 | 用例 | 预期 | 对应测试 |
| --- | --- | --- | --- |
| TC-R-1 | 创作器确定性 | 同输入两次生成 JSON 全等 | `test_composer.test_deterministic` |
| TC-R-2 | 插画确定性 | 同 seed 同场景两图逐字节相等 | `test_tts.TestIllustrationDeterminism` |
| TC-R-3 | 句子切分 | 按句号/问号/叹号切分，引号完整 | `TestSplitSentences` |
| TC-R-4 | 说话人判定 | 引号前缀归属；叙述句一律旁白 | `TestAssignVoice`（含 TC-R-4 回归用例） |
| TC-R-5 | 静音降级 | 0.5s 静音 WAV 帧数精确 | `TestDegrade.test_silence_wav` |
| TC-R-6 | 存取回环 | save→load 后标题/场景数一致 | `test_save_load_roundtrip` |

## 4. Prompt 测试用例（在线模式，密钥就绪后执行）

| 编号 | 用例 | 方法 | 通过标准 |
| --- | --- | --- | --- |
| TC-P-1 | JSON 模式输出 | 3 组固定创意 × story_v3 Prompt | schema 校验 3/3 通过 |
| TC-P-2 | 角色一致性描述 | 检查各场景 visual_prompt 主角外貌字段 | 逐场景外貌描述一致 |
| TC-P-3 | 上下文注入 | 检索 context 是否被引用 | 生成文本至少体现 1 个素材要素 |
| TC-P-4 | JSON 修复链 | 人为喂损坏 JSON 走 chat_json | 第二次修复成功 |

> 注：本机当前无 LLM 密钥，TC-P 组在线补测后回填结果至 `test_report.md` §5。
