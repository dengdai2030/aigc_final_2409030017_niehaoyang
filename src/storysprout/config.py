"""全局配置：路径、.env、三个模态的 provider 开关。

设计原则：所有密钥只从环境变量 / .env 读取；任何外部依赖缺失时
自动落到离线降级模式（mock / local / off），保证 Demo 永远能跑。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
CACHE_DIR = ROOT / ".cache"
LOG_DIR = ROOT / "logs"
WEB_DIR = Path(__file__).resolve().parent / "web"

for _d in (DATA_DIR, OUTPUT_DIR, CACHE_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "video"
BOOK_DIR = OUTPUT_DIR / "book"
IMAGE_DIR = OUTPUT_DIR / "images"
for _d in (AUDIO_DIR, VIDEO_DIR, BOOK_DIR, IMAGE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    """极简 .env 解析（30 行内实现语义），已存在的环境变量优先。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


@dataclass
class LLMConfig:
    # openai=在线（OpenAI 兼容接口）；mock=离线模板创作器
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    temperature: float = 0.8
    max_tokens: int = 4096
    timeout: int = 90
    max_retries: int = 3
    # 成本估算单价（元/千 token，本地估算用）
    price_in_per_1k: float = 0.001
    price_out_per_1k: float = 0.002


@dataclass
class ImageConfig:
    # dashscope=通义万相（在线）；local=本地 PIL 程序化插画（离线）
    provider: str = field(default_factory=lambda: os.getenv("IMAGE_PROVIDER", "local"))
    api_key: str = field(default_factory=lambda: os.getenv("IMAGE_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("IMAGE_MODEL", "wanx2.1-t2i-turbo"))
    size: tuple[int, int] = (1280, 720)
    seed: int = 20261109          # 角色一致性：全局固定 seed
    price_per_image: float = 0.14


@dataclass
class TTSConfig:
    # edge=Edge TTS（免费，需联网）；off=静音时间轴降级
    provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge"))
    voice_map: dict = field(default_factory=lambda: {
        "narrator": "zh-CN-XiaoxiaoNeural",
        "protagonist": "zh-CN-XiaoyiNeural",
        "friend": "zh-CN-YunxiNeural",
        "mentor": "zh-CN-YunjianNeural",
    })
    role_map: dict = field(default_factory=lambda: {})  # 角色名 → voice_key，运行时填充


LLM = LLMConfig()
IMAGE = ImageConfig()
TTS = TTSConfig()
