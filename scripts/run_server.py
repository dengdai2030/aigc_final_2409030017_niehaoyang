"""启动本地 Web 服务：python scripts/run_server.py [port]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from storysprout.server import main  # noqa: E402

if __name__ == "__main__":
    main(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
