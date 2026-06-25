from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


def item_name_to_texture_id(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


class VersionService:
    def list_versions(self) -> list[str]:
        root = get_settings().minecraft_versions_path
        if not root.exists():
            return []

        versions: set[str] = set()
        for jar_path in root.glob("*.jar"):
            versions.add(jar_path.stem)

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if self._has_version_data(entry.name):
                versions.add(entry.name)

        return sorted(versions)

    def resolve_jar_path(self, version: str) -> Path | None:
        root = get_settings().minecraft_versions_path
        candidates = (
            root / f"{version}.jar",
            root / version / f"{version}.jar",
            root / version / "client.jar",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def list_item_icons(self, version: str) -> list[str]:
        icons: set[str] = set()
        for directory in (self._rendered_icons_dir(version), self._legacy_textures_dir(version)):
            if directory is None:
                continue
            for path in directory.glob("*.png"):
                icons.add(path.name)
        return sorted(icons)

    def resolve_item_icon_path(self, version: str, filename: str) -> Path | None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        for directory in (self._rendered_icons_dir(version), self._legacy_textures_dir(version)):
            if directory is None:
                continue
            candidate = directory / safe_name
            if candidate.is_file():
                return candidate
        return None

    def renderer_jar_path(self, version: str) -> str | None:
        local_jar = self.resolve_jar_path(version)
        if local_jar is None:
            return None

        root = get_settings().renderer_minecraft_root.rstrip("/")
        flat_jar = get_settings().minecraft_versions_path / f"{version}.jar"
        if local_jar.resolve() == flat_jar.resolve():
            return f"{root}/{version}.jar"
        return f"{root}/{version}/{local_jar.name}"

    def renderer_output_dir(self, version: str) -> str:
        root = get_settings().renderer_minecraft_root.rstrip("/")
        return f"{root}/{version}/rendered-icons"

    def ensure_rendered_icons_dir(self, version: str) -> Path:
        directory = self._version_dir(version) / "rendered-icons"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def list_rendered_icon_ids(self, version: str) -> set[str]:
        directory = self._rendered_icons_dir(version)
        if directory is None:
            return set()
        return {path.stem for path in directory.glob("*.png")}

    def _has_version_data(self, version: str) -> bool:
        version_dir = self._version_dir(version)
        if not version_dir.is_dir():
            return False
        return (
            self.resolve_jar_path(version) is not None
            or (version_dir / "recipe").is_dir()
            or (version_dir / "rendered-icons").is_dir()
            or (version_dir / "item-textures").is_dir()
        )

    def _version_dir(self, version: str) -> Path:
        return get_settings().minecraft_versions_path / version

    def _rendered_icons_dir(self, version: str) -> Path | None:
        directory = self._version_dir(version) / "rendered-icons"
        if directory.is_dir():
            return directory
        return None

    def _legacy_textures_dir(self, version: str) -> Path | None:
        directory = self._version_dir(version) / "item-textures"
        if directory.is_dir():
            return directory
        return None


@lru_cache
def get_version_service() -> VersionService:
    return VersionService()


version_service = get_version_service()
