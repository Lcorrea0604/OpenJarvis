"""Local HUD for JARVIS: an animated arc-reactor page that mirrors the voice loop.

``jarvis chat --hands-free --hud`` starts a tiny HTTP server on
``127.0.0.1:8765`` (loopback only) that serves ``hud/index.html`` and streams
state changes to it with Server-Sent Events:

* ``{"type": "state", "state": "idle|awake|listening|thinking|speaking|error"}``
* ``{"type": "level", "value": 0..1}``  — microphone level while listening
* ``{"type": "heard", "text": ...}``    — what Jarvis understood
* ``{"type": "reply", "text": ...}``    — what Jarvis answered

Only the standard library is used, so the HUD adds no dependencies.
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765
_HTML_PATH = Path(__file__).parent / "hud" / "index.html"
_LEVEL_FULL_SCALE = 6000.0  # RMS that maps to a full-height voice ring
_LEVEL_MIN_INTERVAL = 0.05  # send at most ~20 level updates per second


class NullHud:
    """No-op HUD used when ``--hud`` is not given."""

    def set_state(self, state: str) -> None:
        pass

    def set_level(self, rms: float) -> None:
        pass

    def heard(self, text: str) -> None:
        pass

    def reply(self, text: str) -> None:
        pass

    def stop(self) -> None:
        pass


class HudServer(NullHud):
    """Serve the HUD page and broadcast events to every open browser tab."""

    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> None:
        self._subscribers: list[queue.Queue[str]] = []
        self._lock = threading.Lock()
        self._last: dict[str, dict[str, Any]] = {}
        self._last_level_at = 0.0
        hud = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # quiet
                logger.debug("hud: " + fmt, *args)

            def do_GET(self) -> None:  # noqa: N802 (http.server API)
                if self.path in ("/", "/index.html"):
                    body = _HTML_PATH.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/events":
                    hud._stream(self)
                else:
                    self.send_error(404)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self.url = f"http://{host}:{self.port}/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    # -- streaming ---------------------------------------------------------

    def _stream(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()

        q: queue.Queue[str] = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
            # Replay the latest state so a freshly opened tab is in sync.
            for event in self._last.values():
                q.put_nowait(json.dumps(event, ensure_ascii=False))
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    chunk = f"data: {data}\n\n"
                except queue.Empty:
                    chunk = ": keep-alive\n\n"
                handler.wfile.write(chunk.encode("utf-8"))
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with self._lock:
                if q in self._subscribers:
                    self._subscribers.remove(q)

    def _broadcast(self, event: dict[str, Any], remember: bool = True) -> None:
        data = json.dumps(event, ensure_ascii=False)
        with self._lock:
            if remember:
                self._last[event["type"]] = event
            for q in list(self._subscribers):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass  # a stalled tab must not block the voice loop

    # -- public API ----------------------------------------------------------

    def set_state(self, state: str) -> None:
        self._broadcast({"type": "state", "state": state})

    def set_level(self, rms: float) -> None:
        now = time.monotonic()
        if now - self._last_level_at < _LEVEL_MIN_INTERVAL:
            return
        self._last_level_at = now
        value = max(0.0, min(1.0, float(rms) / _LEVEL_FULL_SCALE))
        self._broadcast({"type": "level", "value": round(value, 3)}, remember=False)

    def heard(self, text: str) -> None:
        self._broadcast({"type": "heard", "text": text})

    def reply(self, text: str) -> None:
        self._broadcast({"type": "reply", "text": text})

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def open_hud_window(url: str) -> None:
    """Open the HUD as a chromeless app window when possible (Edge/Chrome)."""
    if sys.platform == "win32":
        # Edge ships with every Windows 10/11 install; --app hides the tabs
        # and address bar so the HUD looks like its own window.
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", "msedge", f"--app={url}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    webbrowser.open(url)


def start_hud(console: Any, port: int = DEFAULT_PORT, open_window: bool = True) -> Any:
    """Start the HUD server (or return a NullHud if the port is busy)."""
    try:
        hud = HudServer(port=port)
    except OSError as exc:
        console.print(
            f"[yellow]No se pudo iniciar el HUD en el puerto {port}: {exc}. "
            "Sigo sin HUD.[/yellow]"
        )
        return NullHud()
    console.print(f"[cyan]HUD de Jarvis:[/cyan] {hud.url}")
    if open_window:
        try:
            open_hud_window(hud.url)
        except Exception:
            logger.debug("Could not open HUD window", exc_info=True)
    return hud


__all__ = ["DEFAULT_PORT", "HudServer", "NullHud", "open_hud_window", "start_hud"]
