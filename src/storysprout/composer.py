"""离线模板创作器（LLM 降级方案）。

目标不是替代大模型的创造力，而是保证：
1. 无密钥 / 断网 / API 故障时，端到端流程仍然可演示、可测试；
2. 输出确定性（同输入同输出），让单元测试可以精确断言；
3. 结构与在线模式完全一致（同一个 Story schema）。

生成策略：六幕情绪弧（好奇→期待→挑战→低谷→转机→圆满）+ 世界意象库
+ 主角特征卡。文本为槽位填充，叙事模板带 2-3 处变体，由输入哈希选择。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .schema import Character, Scene, Story

# 六幕情绪弧：mood → (情绪标签, 画面基调色)
BEATS = [
    ("好奇", "清晨的天空，柔和的米金色"),
    ("期待", "明亮的白昼，天蓝与草绿"),
    ("挑战", "风云突变，深蓝与灰紫"),
    ("低谷", "黄昏微光，暗金与雾蓝"),
    ("转机", "破云的光，暖橙与浅金"),
    ("圆满", "星空或彩霞，温柔的紫金"),
]

# 世界意象库：场景关键词 → (场景名词, 视觉元素, 挑战, 转机道具)
WORLDS = {
    "太空": ("星际", "流星、行星环、空间站", "推进器在陨石带里熄了火", "一枚会唱歌的星核水晶"),
    "森林": ("老森林", "苔藓、萤火虫、巨树", "浓雾把回家的路吞掉了", "一盏藏着风声的小灯笼"),
    "海洋": ("深海", "珊瑚、气泡、发光鱼群", "洋流把小船推进了黑水沟", "一块会发光的月亮贝壳"),
    "城市": ("夜晚的城市", "路灯、天台、便利店的灯", "停电把整条街按了静音", "一盒爷爷留下的旧蜡烛"),
    "沙漠": ("沙丘", "驼铃、绿洲、星空", "沙暴盖住了星星", "一口会讲故事的古老水井"),
}

PALETTES = [
    {"hair": "#5b3a29", "cloth": "#ff8a65", "accent": "#ffd54f"},
    {"hair": "#2f2f2f", "cloth": "#4fc3f7", "accent": "#fff176"},
    {"hair": "#6d4c41", "cloth": "#aed581", "accent": "#ffab91"},
]

FRIEND_NAMES = ["墨墨", "阿灯", "小满", "粒粒", "布布"]


@dataclass
class StoryRequest:
    idea: str
    protagonist: str = "小满"
    age: int = 6
    scene: str = "森林"
    theme: str = "勇气与友谊"
    n_scenes: int = 6
    audience_age: int = 6
    length: str = "标准"            # 短篇/标准/加长

    @classmethod
    def from_dict(cls, d: dict) -> "StoryRequest":
        base = cls.__dataclass_fields__  # noqa: F841
        return cls(
            idea=str(d.get("idea", "")).strip() or "一段温暖的冒险",
            protagonist=str(d.get("protagonist", "小满")).strip()[:8] or "小满",
            age=int(d.get("age", 6)),
            scene=str(d.get("scene", "森林")).strip()[:12] or "森林",
            theme=str(d.get("theme", "勇气与友谊")).strip()[:12] or "勇气与友谊",
            n_scenes=max(4, min(8, int(d.get("n_scenes", 6)))),
            audience_age=int(d.get("audience_age", 6)),
            length=str(d.get("length", "标准")),
        )


def _pick(options: list[str], key: str, salt: int = 0) -> str:
    h = hashlib.sha256((key + str(salt)).encode("utf-8")).hexdigest()
    return options[int(h, 16) % len(options)]


def _world(scene: str) -> tuple[str, str, str, str]:
    for k, v in WORLDS.items():
        if k in scene or k in scene[::-1]:
            return v
    # 未知世界：拿默认模板但保留用户的世界名
    return (scene, "微风、光影、远处的小路", "天色忽然暗了下来", "一件被时光藏起来的小礼物")


def _sentences(beat: int, req: StoryRequest, w: tuple, friend: str) -> list[str]:
    """每一幕的 4-6 句叙述，槽位填充 + 模板变体。"""
    place, imagery, crisis, item = w
    hero, age = req.protagonist, req.age
    idea = req.idea.rstrip("。！？")
    if beat == 0:
        return [
            f"{hero}今年{age}岁，最爱做的事，就是趴在窗边想{idea}的样子。",
            f"这天夜里，{hero}在日记本的最后一页写下：\u201c我想去看看{place}。\u201d",
            f"没想到字刚写完，书桌上的小台灯轻轻晃了三下，一个巴掌大的光团从灯罩里钻了出来。",
            f"\u201c我是{friend}，光里住着的声音。\u201d光团眨了眨，\u201c你写下的愿望，我帮你实现一半，另一半，要你自己走。\u201d",
        ]
    if beat == 1:
        return [
            f"第二天一早，{hero}背上小包出发了。{place}的风带着{imagery.split('、')[0]}的味道。",
            f"{friend}飘在前面带路，一路上把{imagery.split('、')[1] if '、' in imagery else imagery}指给{hero}看。",
            f"\u201c原来{place}比我想的还要大！\u201d{hero}越走越快，影子在身后跳格子。",
            f"他们约好：天黑前赶到{place}的深处，看一眼只有勇敢的人才能看见的风景。",
        ]
    if beat == 2:
        return [
            f"可是走到一半，意外发生了——{crisis}。",
            f"四周安静得能听见心跳，{friend}的光也变得忽明忽暗。",
            f"\u201c别怕，\u201d{hero}深吸一口气，把声音放得又稳又慢，\u201c我们先找一块能站住的地方。\u201d",
        ]
    if beat == 3:
        return [
            f"等待的时间里，{hero}有点想家了，鼻子酸酸的。",
            f"{friend}把光调得暖暖的：\u201c害怕不丢人，害怕说明你在乎。\u201d",
            f"{hero}想了想，从口袋里摸出出发时带的小东西，握在手心里，慢慢就不抖了。",
        ]
    if beat == 4:
        return [
            f"就在这时，{item}亮了起来，像有人在对{hero}轻声说：往这边走。",
            f"{hero}和{friend}顺着光，一步、一步，稳稳地穿过了最难的那段路。",
            f"\u201c你看，\u201d{friend}笑了，\u201c另一半愿望，你自己走到了。\u201d",
        ]
    return [
        f"{place}的尽头，{hero}看到了那片只属于勇敢者的风景，风把笑声送出去很远。",
        f"回家的路上，{hero}把{item}的故事讲给{friend}听，两个人约好下一次一起去更远的地方。",
        f"那天晚上，日记本翻回最后一页，{hero}在愿望下面添了一行字：\u201c原来{req.theme}，是自己一步一步走出来的。\u201d",
    ]


def compose_story(req: StoryRequest) -> Story:
    """由 StoryRequest 确定性地生成一个 Story。"""
    w = _world(req.scene)
    friend = _pick(FRIEND_NAMES, req.idea + req.scene, salt=1)
    hero_palette = PALETTES[int(hashlib.sha256(req.protagonist.encode()).hexdigest(), 16) % len(PALETTES)]
    friend_palette = PALETTES[(int(hashlib.sha256(friend.encode()).hexdigest(), 16) + 1) % len(PALETTES)]

    characters = [
        Character(name=req.protagonist,
                  traits=f"{req.age}岁，{req.theme.split('与')[0]}、爱提问",
                  appearance=f"穿{hero_palette['cloth'].strip('#')}色系衣服的小探险家",
                  voice="protagonist", palette=hero_palette),
        Character(name=friend,
                  traits="会发光的小向导，话不多但很稳",
                  appearance="巴掌大的光团，暖黄色光晕",
                  voice="friend", palette=friend_palette),
    ]

    n = min(req.n_scenes, len(BEATS))
    scenes = []
    for i in range(n):
        beat_idx = round(i * (len(BEATS) - 1) / max(n - 1, 1))
        mood, tone = BEATS[beat_idx]
        text = "".join(s + "。" if not s.endswith("。") and not s.endswith("”") else s
                       for s in _sentences(beat_idx, req, w, friend))
        scenes.append(Scene(
            scene_id=i + 1,
            description=f"第{i + 1}幕 · {mood}：{w[0]}，{tone}",
            text=text,
            mood=mood,
            visual_prompt=(
                f"儿童绘本插画，{w[0]}，{w[1]}，{tone}色调，"
                f"主角{req.protagonist}（{characters[0].appearance}）在画面中心，"
                f"柔和光晕，扁平风，暖色，高清"
            ),
        ))

    title = f"《{req.scene}里的{w[3].replace('一枚', '').replace('一块', '').replace('一盏', '').replace('一口', '')}》"
    return Story(
        title=title,
        characters=characters,
        scenes=scenes,
        moral=f"{req.theme}不是等来的，是在路上一点一点长出来的。",
        meta={"source": "composer", "request": req.__dict__},
    )
