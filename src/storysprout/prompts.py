"""Prompt 模板（版本化）。

每条 Prompt 带 vN 版本号：改 Prompt 必须升版本并保留旧版可切换，
这是第 10 周提案里"Prompt 版本化管理"的落点。
"""
from __future__ import annotations

from .composer import StoryRequest

PROMPTS: dict[str, str] = {
    # v3：结构化 + 自检（前八周作业1 中胜出的 S4 策略，本项目沿用）
    "story_v3": """你是一位专业的儿童故事作家。请根据【故事需求】创作一个完整的儿童故事。

【故事需求】
- 主角：{protagonist}，{age}岁
- 世界/场景：{scene}
- 主题：{theme}
- 故事创意：{idea}
- 目标读者年龄：{audience_age} 岁
- 场景数量：{n_scenes} 个（情节要有起伏：好奇→期待→挑战→低谷→转机→圆满）

<参考素材>
{context}
</参考素材>

【输出要求】
1. 只输出一个 JSON 对象，不要任何解释或 Markdown 代码块；
2. 结构如下：
{{
  "title": "故事标题（8字以内，有童趣）",
  "characters": [
    {{"name": "角色名", "traits": "性格特征", "appearance": "外貌描述（具体到颜色，供文生图保持一致）", "voice": "protagonist|friend|mentor"}}
  ],
  "scenes": [
    {{"scene_id": 1, "description": "场景描述", "text": "该场景的故事正文（120-200字，含对话，对话用引号）", "mood": "情绪基调（好奇/期待/挑战/低谷/转机/圆满）", "visual_prompt": "适合文生图的中文描述，包含场景+角色外貌+画风"}}
  ],
  "moral": "故事寓意（一句话，不说教）"
}}
3. 输出前自检：characters 至少 2 人；每个 scene 的 text ≥ 100 字；scene_id 从 1 连续编号；visual_prompt 中主角外貌描述逐场景保持一致。
""",
}

STORY_KEY = "story_v3"


def build_story_prompt(req: StoryRequest, context: str = "") -> tuple[str, str]:
    """返回 (system, user)。"""
    system = "你是专业的儿童故事作家与多模态内容策划，输出永远是一个合法 JSON 对象。"
    user = PROMPTS[STORY_KEY].format(
        protagonist=req.protagonist, age=req.age, scene=req.scene,
        theme=req.theme, idea=req.idea, audience_age=req.audience_age,
        n_scenes=req.n_scenes,
        context=context or "（无）",
    )
    return system, user
