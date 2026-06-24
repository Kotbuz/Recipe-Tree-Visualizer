from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class VersionService:
    def list_versions(self) -> list[str]:
        root = get_settings().minecraft_versions_path
        if not root.exists():
            return []

        versions: list[str] = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            textures_dir = entry / "item-textures"
            if textures_dir.is_dir():
                versions.append(entry.name)
        return versions

    def list_item_icons(self, version: str) -> list[str]:
        textures_dir = self._textures_dir(version)
        if textures_dir is None:
            return []

        icons: list[str] = []
        for path in sorted(textures_dir.glob("*.png")):
            icons.append(path.name)
        return icons

    def resolve_item_icon_path(self, version: str, filename: str) -> Path | None:
        textures_dir = self._textures_dir(version)
        if textures_dir is None:
            return None

        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        candidate = textures_dir / safe_name
        if candidate.is_file():
            return candidate
        return None

    def _textures_dir(self, version: str) -> Path | None:
        root = get_settings().minecraft_versions_path
        textures_dir = root / version / "item-textures"
        if textures_dir.is_dir():
            return textures_dir
        return None


@lru_cache
def get_version_service() -> VersionService:
    return VersionService()


version_service = get_version_service()
