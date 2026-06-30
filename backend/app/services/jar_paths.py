from __future__ import annotations

from pathlib import Path

from app.services.version_service import version_service


def collect_profile_jar_paths(version: str, *, profile_id: str | None = None) -> list[Path]:
    """client.jar версии + mods/*.jar активного профиля (R1a)."""
    jars: list[Path] = []
    client_jar = version_service.resolve_jar_path(version)
    if client_jar is not None:
        jars.append(client_jar)
    mods_dir = version_service.mods_dir(version, profile_id)
    if mods_dir.is_dir():
        jars.extend(sorted(path for path in mods_dir.glob("*.jar") if path.is_file()))
    return jars
