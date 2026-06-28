#!/usr/bin/env python3
"""HTTP API for NeoForge in-game recipe export (1.21.1+)."""

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

EXPORT_SCRIPT = Path(os.environ.get("EXPORT_SCRIPT", "/opt/rtv-recipe-exporter-neo/run-neo-export.sh"))
EXPORT_TIMEOUT_SECONDS = int(os.environ.get("EXPORT_TIMEOUT_SECONDS", "3600"))
SUPPORTED_MINECRAFT_VERSIONS = {
    version.strip()
    for version in os.environ.get("SUPPORTED_MINECRAFT_VERSIONS", "1.21.1").split(",")
    if version.strip()
}

_lock = threading.Lock()
_busy = False
_last_result: dict[str, Any] | None = None


def _run_export(payload: dict[str, Any]) -> dict[str, Any]:
    global _last_result

    minecraft_version = str(payload.get("minecraft_version", "")).strip()
    if minecraft_version not in SUPPORTED_MINECRAFT_VERSIONS:
        return {
            "status": "error",
            "error": f"unsupported minecraft version (supported: {sorted(SUPPORTED_MINECRAFT_VERSIONS)})",
        }

    instance_path = str(payload.get("instance_path", "")).strip()
    output_dir = str(payload.get("output_dir", "")).strip()
    loader_version = str(payload.get("loader_version", "")).strip()
    if not instance_path or not output_dir or not loader_version:
        return {
            "status": "error",
            "error": "instance_path, output_dir and loader_version are required",
        }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MINECRAFT_VERSION"] = minecraft_version
    env["INSTANCE_PATH"] = instance_path
    env["OUTPUT_DIR"] = output_dir
    env["LOADER_VERSION"] = loader_version
    env["STORAGE_VERSION"] = str(payload.get("storage_version", "")).strip()
    env["PROFILE_ID"] = str(payload.get("profile_id", "default")).strip() or "default"

    started = time.time()
    try:
        completed = subprocess.run(
            [str(EXPORT_SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        result = {
            "status": "error",
            "error": "export timed out",
            "duration_seconds": round(time.time() - started, 2),
        }
        _last_result = result
        return result
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        result = {
            "status": "error",
            "error": detail or "export failed",
            "duration_seconds": round(time.time() - started, 2),
            "log_tail": detail[-8000:] if detail else None,
        }
        _last_result = result
        return result

    snapshot = Path(output_dir) / "recipes.baked.json"
    recipe_count = 0
    if snapshot.is_file():
        try:
            body = json.loads(snapshot.read_text(encoding="utf-8"))
            recipes = body.get("recipes")
            if isinstance(recipes, dict):
                recipe_count = len(recipes)
        except json.JSONDecodeError:
            pass

    log_tail = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    log_tail = log_tail.strip()[-8000:] if log_tail.strip() else None

    result = {
        "status": "ok",
        "recipe_count": recipe_count,
        "duration_seconds": round(time.time() - started, 2),
        "log_tail": log_tail,
    }
    _last_result = result
    return result


class ExportHandler(BaseHTTPRequestHandler):
    server_version = "RTVNeoRecipeExporter/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[neo-export-server] {self.address_string()} - {format % args}")

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
                    "supported_minecraft_versions": sorted(SUPPORTED_MINECRAFT_VERSIONS),
                },
            )
            return
        if path == "/status":
            self._send_json(200, {"busy": _busy, "last_result": _last_result})
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

        if not _lock.acquire(blocking=False):
            self._send_json(409, {"error": "export already in progress"})
            return

        _busy = True
        try:
            result = _run_export(payload)
        finally:
            _busy = False
            _lock.release()

        status_code = 200 if result.get("status") == "ok" else 500
        self._send_json(status_code, result)


def main() -> None:
    port = int(os.environ.get("PORT", "8091"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), ExportHandler)
    print(
        f"[neo-export-server] listening on {host}:{port}, "
        f"versions={sorted(SUPPORTED_MINECRAFT_VERSIONS)}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
