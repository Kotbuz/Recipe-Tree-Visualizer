from __future__ import annotations

import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.config import get_settings
from app.services.icon_name_resolver import resolve_icon_item_name


def item_name_to_texture_id(name: str, version: str | None = None) -> str:
    return resolve_icon_item_name(name, version=version).strip().lower().replace(" ", "_")


def _texture_id_variants(icon_id: str) -> tuple[str, ...]:
    variants = [icon_id]
    if icon_id.endswith("s") and not icon_id.endswith("ss"):
        variants.append(icon_id[:-1])
    return tuple(dict.fromkeys(variants))


def texture_id_from_icon_filename(filename: str) -> str:
    display_name = Path(filename).name.removesuffix(".png").replace("_", " ")
    return item_name_to_texture_id(display_name)


class VersionService:
    def list_installed_versions(self) -> list[str]:
        root = get_settings().minecraft_versions_path
        if not root.exists():
            return []

        versions: set[str] = set()
        for jar_path in root.glob("*.jar"):
            versions.add(jar_path.stem)

        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if self.is_version_installed(entry.name):
                versions.add(entry.name)

        return sorted(versions)

    def list_versions(self) -> list[str]:
        return self.list_installed_versions()

    def is_version_installed(self, version: str) -> bool:
        return self.resolve_jar_path(version) is not None

    def client_jar_path(self, version: str) -> Path:
        return self._version_dir(version) / "client.jar"

    def mods_dir(self, version: str) -> Path:
        return self._version_dir(version) / "mods"

    def recipe_dir(self, version: str) -> Path:
        return self._version_dir(version) / "recipe"

    def ensure_version_layout(self, version: str) -> Path:
        version_dir = self._version_dir(version)
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "mods").mkdir(exist_ok=True)
        (version_dir / "recipe").mkdir(exist_ok=True)
        (version_dir / "rendered-icons").mkdir(exist_ok=True)
        return version_dir

    def resolve_default_version(self) -> str | None:
        configured = get_settings().minecraft_default_version.strip()
        installed = self.list_installed_versions()
        if configured and configured in installed:
            return configured
        if configured:
            for version in installed:
                if version == configured:
                    return version
        return installed[0] if installed else None

    def resolve_jar_path(self, version: str) -> Path | None:
        root = get_settings().minecraft_versions_path
        candidates = (
            root / version / "client.jar",
            root / version / f"{version}.jar",
            root / f"{version}.jar",
        )

        best: Path | None = None
        best_size = 0
        for candidate in candidates:
            if not candidate.is_file():
                continue
            size = candidate.stat().st_size
            if size > best_size:
                best = candidate
                best_size = size

        return best if best_size > 1024 else None

    def list_item_icons(self, version: str) -> list[str]:
        icons: set[str] = set()
        rendered_dir = self._rendered_icons_dir(version)

        for directory in (rendered_dir, self._legacy_textures_dir(version)):
            if directory is None:
                continue
            for path in directory.glob("*.png"):
                icons.add(path.name)

        # Пока renderer ещё не создал rendered-icons, даём манифест из рецептов
        # (с jar-fallback). После появления папки — только реальные PNG, без
        # «фантомных» имён, иначе браузер кэширует плоские текстуры из jar.
        if not icons and self.resolve_jar_path(version) is not None:
            icons.update(self._recipe_icon_filenames(version))

        return sorted(icons)

    def icons_revision(self, version: str) -> str:
        rendered_dir = self._rendered_icons_dir(version)
        if rendered_dir is None:
            return "0"

        files = list(rendered_dir.glob("*.png"))
        if not files:
            return "0"

        latest_mtime = max(path.stat().st_mtime for path in files)
        return f"{len(files)}-{int(latest_mtime)}"

    def build_ingredient_index(self, version: str) -> dict[str, object]:
        from app.recipes.registry import get_version_ingredient_registry

        registry = get_version_ingredient_registry(version)
        tags = {
            tag_id: registry.resolve_tag(tag_id)
            for tag_id in registry.list_tag_ids()
        }
        return {
            "version": version,
            "tags": tags,
            "aliases": registry.aliases,
        }

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

        if self._rendered_icons_dir(version) is not None:
            return None

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
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for variant_id in _texture_id_variants(icon_id):
                    candidates = (
                        f"assets/minecraft/textures/item/{variant_id}.png",
                        f"assets/minecraft/textures/block/{variant_id}.png",
                    )
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
        return self.is_version_installed(version)

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
        from app.services.icon_registry import collect_recipe_icon_ids

        return {f"{icon_id}.png" for icon_id in collect_recipe_icon_ids(version)}


@lru_cache
def get_version_service() -> VersionService:
    return VersionService()


version_service = get_version_service()
