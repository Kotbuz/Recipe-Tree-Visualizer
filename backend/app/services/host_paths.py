from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[/\\]")


def is_windows_absolute_path(value: str) -> bool:
    return bool(_WINDOWS_DRIVE_RE.match(value.strip()))


def format_stored_path_for_display(raw: str) -> str:
    text = raw.strip()
    if not text:
        return text
    if is_windows_absolute_path(text):
        return str(PureWindowsPath(text))
    return text


def _default_host_path_mappings() -> str:
    host = os.environ.get("INSTANCES_HOST_PATH", "").strip()
    if not host:
        return ""
    container = os.environ.get("INSTANCES_CONTAINER_PATH", "/host/instances").strip()
    if not container:
        return ""
    windows_prefix = format_stored_path_for_display(host)
    return f"{windows_prefix}={container}"


def _load_host_path_mappings() -> list[tuple[PureWindowsPath, Path]]:
    raw = os.environ.get("HOST_PATH_MAPPINGS", "").strip() or _default_host_path_mappings()
    mappings: list[tuple[PureWindowsPath, Path]] = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        windows_prefix, container_prefix = entry.split("=", 1)
        windows_prefix = windows_prefix.strip()
        container_prefix = container_prefix.strip()
        if not windows_prefix or not container_prefix:
            continue
        mappings.append((PureWindowsPath(windows_prefix), Path(container_prefix)))
    return mappings


def map_windows_path_to_container(windows_path: PureWindowsPath) -> Path | None:
    normalized = PureWindowsPath(
        *windows_path.parts,
    )
    for windows_prefix, container_root in _load_host_path_mappings():
        try:
            relative = normalized.relative_to(windows_prefix)
        except ValueError:
            continue
        return Path(str(container_root)).joinpath(*relative.parts)
    return None


def resolve_host_filesystem_path(raw: str) -> Path:
    """Разрешает путь из profile.json без склейки с cwd на Linux/Docker."""
    text = raw.strip()
    if not text:
        raise ValueError("Пустой путь")

    if is_windows_absolute_path(text):
        windows_path = PureWindowsPath(text)
        mapped = map_windows_path_to_container(windows_path)
        if mapped is not None:
            return mapped

        if os.name == "nt":
            return Path(text).expanduser().resolve()

        # На Linux/Docker Windows-путь не делаем .resolve() — иначе получится
        # /app/backend/C:\Users\...
        return Path(text.replace("\\", "/"))

    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    return path.resolve()


def host_path_unavailable_hint(raw: str) -> str | None:
    if os.name == "nt" or not is_windows_absolute_path(raw):
        return None
    if map_windows_path_to_container(PureWindowsPath(raw)) is not None:
        return None
    return (
        "Бэкенд запущен в Linux/Docker и не видит диск Windows напрямую. "
        "Смонтируйте папку instances в контейнер, задайте INSTANCES_HOST_PATH в .env "
        "(см. .env.example и docker-compose.yml), либо запускайте backend локально на Windows."
    )
