"""Local interactive workspace. Observations are generated only on an explicit POST."""

from __future__ import annotations

import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import urlsplit

from .viewer import build_viewer


def serve_workspace(data: dict[str, Any], observation_config: dict[str, Any],
                    observation_seed: int, collect: Callable[[], Path], *,
                    port: int = 0, open_browser: bool = True) -> None:
    """Serve the initial truth map, then materialize the expedition exactly once."""
    endpoint = "/collect/" + secrets.token_urlsafe(24)
    with TemporaryDirectory(prefix="geo-workspace-") as directory:
        initial = build_viewer(
            data, Path(directory) / "initial.html",
            observation_config=observation_config, observation_seed=observation_seed,
            collect_endpoint=endpoint,
        )
        current = initial
        collected = False
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def send_bytes(self, status: int, content: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self) -> None:
                if urlsplit(self.path).path != "/":
                    self.send_error(404)
                    return
                with lock:
                    html = current.read_bytes()
                self.send_bytes(200, html, "text/html; charset=utf-8")

            def do_POST(self) -> None:
                nonlocal current, collected
                if self.path != endpoint:
                    self.send_error(404)
                    return
                with lock:
                    if not collected:
                        try:
                            current = collect()
                            collected = True
                        except Exception as error:
                            print(f"Ошибка сбора наблюдений: {error}", flush=True)
                            self.send_bytes(500, b'{"ok":false}', "application/json")
                            return
                self.send_bytes(200, b'{"ok":true}', "application/json")

            def log_message(self, format: str, *args: Any) -> None:
                # Keep the terminal focused on the geological workflow.
                pass

        with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Истинная карта готова. Просмотр: {url}", flush=True)
            print("Предварительные наблюдения ещё не собраны. Нажмите кнопку на вкладке 02.", flush=True)
            print("Для остановки нажмите Ctrl+C.", flush=True)
            if open_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
