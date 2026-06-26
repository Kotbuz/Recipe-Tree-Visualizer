#!/usr/bin/env python3
"""Minimal HTTP API for on-demand Forge recipe export inside Docker."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EXPORT_SCRIPT = Path(os.environ.get("EXPORT_SCRIPT", "/opt/forge/run-export.sh"))
MINECRAFT_ROOT = Path(os.environ.get("MINECRAFT_ROOT", "/data/minecraft"))
SUPPORTED_VERSIONS = {
    version.strip()
    for version in os.environ.get("SUPPORTED_VERSIONS", "1.7.10").split(",")
    if version.strip()
}
EXPORT_TIMEOUT_SECONDS = int(os.environ.get("EXPORT_TIMEOUT_SECONDS", "1800"))

_lock = threading.Lock()
_busy = False
_last_result: dict[str, Any] | None = None


def _count_recipes(version: str) -> int:
    recipe_dir = MINECRAFT_ROOT / version / "recipe"
    if not recipe_dir.is_dir():
        return 0
    return len(
        [
            path
            for path in recipe_dir.glob("*.json")
            if not path.name.startswith("_")
        ]
    )


def _run_export(version: str) -> dict[str, Any]:
    global _busy, _last_result

    if version not in SUPPORTED_VERSIONS:
        return {
            "status": "error",
            "version": version,
            "error": f"unsupported version (supported: {sorted(SUPPORTED_VERSIONS)})",
        }

    recipe_dir = MINECRAFT_ROOT / version / "recipe"
    recipe_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    try:
        completed = subprocess.run(
            [str(EXPORT_SCRIPT), version],
            check=True,
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        result = {
            "status": "error",
            "version": version,
            "error": "export timed out",
            "duration_seconds": round(time.time() - started, 2),
        }
        _last_result = result
        return result
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        result = {
            "status": "error",
            "version": version,
            "error": detail or "export failed",
            "duration_seconds": round(time.time() - started, 2),
        }
        _last_result = result
        return result

    exported = _count_recipes(version)
    result = {
        "status": "ok",
        "version": version,
        "exported": exported,
        "duration_seconds": round(time.time() - started, 2),
    }
    if completed.stdout.strip():
        result["stdout_tail"] = completed.stdout.strip()[-4000:]
    if completed.stderr.strip():
        result["stderr_tail"] = completed.stderr.strip()[-4000:]
    _last_result = result
    return result


class ExportHandler(BaseHTTPRequestHandler):
    server_version = "RTVRecipeExporter/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[export-server] {self.address_string()} - {format % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "busy": _busy,
                    "supported_versions": sorted(SUPPORTED_VERSIONS),
                },
            )
            return
        if path == "/status":
            self._send_json(
                200,
                {
                    "busy": _busy,
                    "last_result": _last_result,
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        global _busy

        path = urlparse(self.path).path
        if path != "/export":
            self._send_json(404, {"error": "not found"})
            return

        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
            return

        version = str(payload.get("version", "")).strip()
        if not version:
            self._send_json(400, {"error": "version is required"})
            return

        force = bool(payload.get("force", False))
        if not force:
            existing = _count_recipes(version)
            if existing > 0:
                self._send_json(
                    200,
                    {
                        "status": "skipped",
                        "version": version,
                        "exported": existing,
                        "reason": "recipe directory already has exports",
                    },
                )
                return

        if not _lock.acquire(blocking=False):
            self._send_json(409, {"error": "export already in progress"})
            return

        _busy = True
        try:
            result = _run_export(version)
        finally:
            _busy = False
            _lock.release()

        status_code = 200 if result.get("status") == "ok" else 500
        self._send_json(status_code, result)


def main() -> None:
    port = int(os.environ.get("PORT", "8090"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), ExportHandler)
    print(
        f"[export-server] listening on {host}:{port}, "
        f"minecraft_root={MINECRAFT_ROOT}, versions={sorted(SUPPORTED_VERSIONS)}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
