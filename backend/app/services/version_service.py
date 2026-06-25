from __future__ import annotations

import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.config import get_settings
from app.services.icon_name_resolver import resolve_icon_item_name


def item_name_to_texture_id(name: str) -> str:
    return resolve_icon_item_name(name).strip().lower().replace(" ", "_")


def texture_id_from_icon_filename(filename: str) -> str:
    display_name = Path(filename).name.removesuffix(".png").replace("_", " ")
    return item_name_to_texture_id(display_name)


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

        if self.resolve_jar_path(version) is not None:
            icons.update(self._recipe_icon_filenames(version))

        return sorted(icons)

    def resolve_item_icon_path(self, version: str, filename: str) -> Path | None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        texture_id = texture_id_from_icon_filename(safe_name)
        resolved_filename = f"{texture_id}.png"

        for directory in (self._rendered_icons_dir(version), self._legacy_textures_dir(version)):
            if directory is None:
                continue
            for candidate_name in {safe_name, resolved_filename}:
                candidate = directory / candidate_name
                if candidate.is_file():
                    return candidate
        return None

    def resolve_item_icon(
        self,
        version: str,
        filename: str,
    ) -> tuple[Literal["file", "bytes"], Path | bytes] | None:
        icon_path = self.resolve_item_icon_path(version, filename)
        if icon_path is not None:
            return ("file", icon_path)

        jar_bytes = self.read_jar_texture_bytes(version, filename)
        if jar_bytes is not None:
            return ("bytes", jar_bytes)

        return None

    def read_jar_texture_bytes(self, version: str, filename: str) -> bytes | None:
        jar_path = self.resolve_jar_path(version)
        if jar_path is None:
            return None

        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        icon_id = texture_id_from_icon_filename(safe_name)
        candidates = (
            f"assets/minecraft/textures/item/{icon_id}.png",
            f"assets/minecraft/textures/block/{icon_id}.png",
        )

        try:
            with zipfile.ZipFile(jar_path) as archive:
                for asset_path in candidates:
                    try:
                        return archive.read(asset_path)
                    except KeyError:
                        continue
        except (OSError, zipfile.BadZipFile):
            return None

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

    def _recipe_icon_filenames(self, version: str) -> set[str]:
        from app.services.recipe_service import recipe_service

        filenames: set[str] = set()
        for recipe in recipe_service.get_recipes(version):
            for item in recipe.inputs + recipe.outputs:
                texture_id = item_name_to_texture_id(item.name)
                filenames.add(f"{texture_id}.png")
        return filenames


@lru_cache
def get_version_service() -> VersionService:
    return VersionService()


version_service = get_version_service()
