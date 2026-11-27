"""Local interactive workspace. Observations are generated only on an explicit POST."""

from __future__ import annotations

import secrets
import threading
import webbrowser
import json
import math
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import urlsplit

from .viewer import build_viewer
from .observations import PRELIMINARY_TABLES, TABLE_FIELDS


def expedition_input(data: dict, config: dict, preliminary: dict | None, payload: dict | None) -> dict:
    """Keep collected measurements intact and validate any manually added records."""
    original = preliminary["tables"] if preliminary is not None else {name: [] for name in PRELIMINARY_TABLES}
    if payload is None:
        if preliminary is None:
            raise ValueError("Сначала соберите предварительные наблюдения")
        return {name: original[name] for name in PRELIMINARY_TABLES}
    if not isinstance(payload, dict) or set(payload) != set(PRELIMINARY_TABLES):
        raise ValueError("Некорректный набор предварительных таблиц")
    if preliminary is None and not any(payload.values()):
        raise ValueError("Сначала соберите или загрузите предварительные наблюдения")
    rocks = {rock["id"]: rock["name"] for rock in data["rocks"]}
    dims = data["dimensions"]
    numeric = set("x_m y_m surface_elevation_m magnetic_anomaly_nt magnetic_sigma_nt gamma_count_rate_cps gamma_sigma_cps position_uncertainty_m elevation_uncertainty_m slope_deg local_relief_m".split())
    signed = {"x_m", "y_m", "surface_elevation_m", "magnetic_anomaly_nt", "local_relief_m"}
    for name, rows in payload.items():
        if not isinstance(rows, list) or len(rows) > 100000:
            raise ValueError(f"Некорректный размер таблицы {name}")
        existing = {row["observation_id"]: row for row in original[name]}
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(TABLE_FIELDS[name]):
                raise ValueError(f"Неверные поля таблицы {name}")
            identifier = row["observation_id"]
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
                raise ValueError(f"Повторяющийся или пустой идентификатор: {name}")
            seen.add(identifier)
            if identifier in existing:
                if row != existing[identifier]:
                    raise ValueError(f"Собранное наблюдение изменено: {identifier}")
                continue
            if row["campaign_id"] != config["campaign_id"]:
                raise ValueError("Наблюдение относится к другой экспедиции")
            for key, value in row.items():
                if value is None and key in {"slope_deg", "local_relief_m"}:
                    continue
                if key in numeric:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value == -999 or (key not in signed and value < 0):
                        raise ValueError(f"Некорректное значение {key}")
                elif not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Не заполнено поле {key}")
            date.fromisoformat(row["survey_date"])
            tolerance = row.get("position_uncertainty_m", 0)
            if not (-tolerance <= row["x_m"] <= dims["width_m"] + tolerance and -tolerance <= row["y_m"] <= dims["height_m"] + tolerance):
                raise ValueError("Точка за пределами участка")
            if name == "outcrop_observations" and rocks.get(row["observed_rock_id"]) != row["observed_rock_name"]:
                raise ValueError("Неизвестная порода в наблюдении обнажения")
            if name == "terrain_observations" and (row["terrain_type"] not in {"hill", "depression", "slope", "flat", "undetermined"} or
                    (row["slope_deg"] is not None and row["slope_deg"] > 90)):
                raise ValueError("Некорректные характеристики рельефа")
        if not existing.keys() <= seen:
            raise ValueError("Отсутствуют ранее собранные наблюдения")
    return payload


def serve_workspace(data: dict[str, Any], observation_config: dict[str, Any],
                    observation_seed: int, collect_preliminary: Callable[[], dict],
                    collect_expedition: Callable[[dict], Path], *,
                    port: int = 0, open_browser: bool = True) -> None:
    """Serve three successive states, generating each stage on its own POST."""
    endpoint = "/collect/" + secrets.token_urlsafe(24)
    expedition_endpoint = "/expedition/" + secrets.token_urlsafe(24)
    with TemporaryDirectory(prefix="geo-workspace-") as directory:
        initial = build_viewer(
            data, Path(directory) / "initial.html",
            observation_config=observation_config, observation_seed=observation_seed,
            collect_endpoint=endpoint, expedition_endpoint=expedition_endpoint,
            expedition_collected=False,
        )
        current = initial
        preliminary = None
        expedition_collected = False
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
                nonlocal current, preliminary, expedition_collected
                if self.path not in {endpoint, expedition_endpoint}:
                    self.send_error(404)
                    return
                with lock:
                    try:
                        if self.path == endpoint and preliminary is None and not expedition_collected:
                            result = collect_preliminary()
                            current = build_viewer(data, Path(directory) / "preliminary.html", observations=result,
                                                   preliminary_collected=True, expedition_collected=False,
                                                   expedition_endpoint=expedition_endpoint)
                            preliminary = result
                        elif self.path == expedition_endpoint and not expedition_collected:
                            size = int(self.headers.get("Content-Length", "0"))
                            if not 0 <= size <= 64 * 1024 * 1024:
                                raise ValueError("Слишком большой пакет наблюдений")
                            payload = json.loads(self.rfile.read(size)) if size else None
                            tables = expedition_input(data, observation_config, preliminary, payload)
                            current = collect_expedition(tables)
                            expedition_collected = True
                    except ValueError as error:
                        self.send_bytes(400, json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False).encode(), "application/json")
                        return
                    except Exception as error:
                        print(f"Ошибка выполнения этапа: {error}", flush=True)
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
