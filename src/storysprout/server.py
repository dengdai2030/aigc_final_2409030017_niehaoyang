"""零依赖本地 Web 服务（标准库 http.server）。

API：
    GET  /                    Web UI
    POST /api/create          {idea, protagonist, age, scene, theme, n_scenes} → 启动创作
    GET  /api/state           当前进度：每步状态/耗时、产物、成本、干预记录
    POST /api/intervene       {instruction} → 中途干预，只重跑受影响步骤
    GET  /outputs/<path>      产物静态文件（图片/音频/视频/PDF）

启动：python -m storysprout.server  （默认 http://127.0.0.1:8000）
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .agent import CaseSpec, RulePlanner, StoryAgent
from .config import OUTPUT_DIR, ROOT, WEB_DIR

LOCK = threading.Lock()
AGENT: StoryAgent | None = None
BUSY = False


def _start_case(payload: dict) -> dict:
    global AGENT, BUSY
    case = CaseSpec(
        idea=str(payload.get("idea", "")).strip() or "一段温暖的冒险",
        protagonist=str(payload.get("protagonist", "小满")).strip() or "小满",
        age=int(payload.get("age", 6)),
        scene=str(payload.get("scene", "森林")).strip() or "森林",
        theme=str(payload.get("theme", "勇气与友谊")).strip() or "勇气与友谊",
        n_scenes=max(4, min(8, int(payload.get("n_scenes", 6)))),
        tag="web",
    )
    AGENT = StoryAgent(planner=RulePlanner())
    BUSY = True

    def worker():
        global BUSY
        try:
            AGENT.run(case)
            AGENT.save_trace(OUTPUT_DIR / "traces" / "trace_web.json")
            AGENT.render_log(OUTPUT_DIR / "traces" / "log_web.md")
        finally:
            BUSY = False

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "tag": case.tag}


def _state() -> dict:
    from .llm import GLOBAL_USAGE

    if AGENT is None:
        return {"busy": False, "started": False, "steps": [], "artifacts": {},
                "usage": GLOBAL_USAGE.summary(), "idea": "", "events": []}
    steps = [
        {"idx": t["idx"], "tool": t["tool"], "status": t["status"],
         "elapsed": t["elapsed"], "summary": t.get("summary", ""),
         "error": t.get("error", "")}
        for t in AGENT.trace if "tool" in t
    ]
    events = [t["msg"] for t in AGENT.trace if "tool" not in t][-30:]
    arts = {}
    for k, v in AGENT.state.items():
        if k in ("story_file", "audio", "video", "book", "timeline"):
            arts[k] = v
    if "images" in AGENT.state:
        arts["images"] = AGENT.state["images"]
    return {"busy": BUSY, "started": True, "steps": steps, "artifacts": arts,
            "usage": GLOBAL_USAGE.summary(), "idea": AGENT.state.get("idea", ""),
            "events": events, "tts_provider": AGENT.state.get("tts_provider", "")}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            body = (WEB_DIR / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
        elif path.startswith("/outputs/"):
            f = ROOT / path.lstrip("/")
            if f.is_file():
                ctype = {".png": "image/png", ".jpg": "image/jpeg", ".mp3": "audio/mpeg",
                         ".mp4": "video/mp4", ".pdf": "application/pdf"}.get(f.suffix, "application/octet-stream")
                self._send(200, f.read_bytes(), ctype)
            else:
                self._send(404, b"not found", "text/plain")
        elif path == "/api/state":
            with LOCK:
                self._json(_state())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        global BUSY
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"ok": False, "error": "bad json"}, 400)

        if path == "/api/create":
            with LOCK:
                if BUSY:
                    return self._json({"ok": False, "error": "已有任务在跑，请稍候"}, 409)
                return self._json(_start_case(payload))
        if path == "/api/intervene":
            with LOCK:
                if AGENT is None or BUSY:
                    return self._json({"ok": False, "error": "当前没有可干预的完成态任务"}, 409)
                result = AGENT.intervene(str(payload.get("instruction", "")))
                AGENT.save_trace(OUTPUT_DIR / "traces" / "trace_web.json")
                AGENT.render_log(OUTPUT_DIR / "traces" / "log_web.md")
                return self._json(result)
        self._json({"ok": False, "error": "unknown endpoint"}, 404)

    def log_message(self, *a):  # 静默默认访问日志
        pass


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    print(f"故事精灵 StorySprout · http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import sys
    main(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
