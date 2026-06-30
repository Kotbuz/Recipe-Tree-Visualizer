from __future__ import annotations

import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.config import get_settings
from app.services.icon_name_resolver import resolve_icon_item_name
from app.services.profile_storage import (
    DEFAULT_PROFILE_ID,
    ensure_profile_subdirs,
    migrate_legacy_version_layout,
    read_active_profile_id,
    write_active_profile_id,
    write_profile_meta,
)


def item_name_to_texture_id(name: str, version: str | None = None) -> str:
    return resolve_icon_item_name(name, version=version).strip().lower().replace(" ", "_")


def _texture_id_variants(icon_id: str) -> tuple[str, ...]:
    variants = [icon_id]
    if icon_id.endswith("s") and not icon_id.endswith("ss"):
        variants.append(icon_id[:-1])
    return tuple(dict.fromkeys(variants))


def texture_id_from_icon_filename(filename: str) -> str:
    stem = Path(filename).name.removesuffix(".png")
    if "_" in stem:
        namespace, _, path = stem.partition("_")
        if namespace not in {"minecraft", "tag"} and path:
            return stem
    display_name = stem.replace("_", " ")
    return item_name_to_texture_id(display_name)


def _mod_icon_id_parts(icon_id: str) -> tuple[str | None, str]:
    if "_" not in icon_id:
        return None, icon_id
    namespace, _, path = icon_id.partition("_")
    if not path or namespace in {"minecraft", "tag"}:
        return None, icon_id
    return namespace, path


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

    def profiles_dir(self, version: str) -> Path:
        return self._version_dir(version) / "profiles"

    def profile_dir(self, version: str, profile_id: str) -> Path:
        return self.profiles_dir(version) / profile_id

    def mods_dir(self, version: str, profile_id: str | None = None) -> Path:
        return self.profile_dir(version, self._resolve_profile_id(version, profile_id)) / "mods"

    def recipe_dir(self, version: str, profile_id: str | None = None) -> Path:
        return self.profile_dir(version, self._resolve_profile_id(version, profile_id)) / "recipe"

    def config_dir(self, version: str, profile_id: str | None = None) -> Path:
        return self.profile_dir(version, self._resolve_profile_id(version, profile_id)) / "config"

    def scripts_dir(self, version: str, profile_id: str | None = None) -> Path:
        return self.profile_dir(version, self._resolve_profile_id(version, profile_id)) / "scripts"

    def kubejs_dir(self, version: str, profile_id: str | None = None) -> Path:
        return self.profile_dir(version, self._resolve_profile_id(version, profile_id)) / "kubejs"

    def ensure_version_layout(self, version: str) -> Path:
        version_dir = self._version_dir(version)
        version_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_profiles_layout(version)
        return version_dir

    def ensure_profiles_layout(self, version: str) -> Path:
        version_dir = self._version_dir(version)
        version_dir.mkdir(parents=True, exist_ok=True)
        migrate_legacy_version_layout(version_dir)

        profiles_dir = self.profiles_dir(version)
        profiles_dir.mkdir(parents=True, exist_ok=True)

        default_profile = self.profile_dir(version, DEFAULT_PROFILE_ID)
        if not default_profile.is_dir():
            ensure_profile_subdirs(default_profile)
            write_profile_meta(
                default_profile,
                profile_id=DEFAULT_PROFILE_ID,
                name="По умолчанию",
                source="default",
            )

        if read_active_profile_id(profiles_dir) is None:
            write_active_profile_id(profiles_dir, DEFAULT_PROFILE_ID)

        return profiles_dir

    def get_active_profile_id(self, version: str) -> str:
        self.ensure_profiles_layout(version)
        active = read_active_profile_id(self.profiles_dir(version))
        return active or DEFAULT_PROFILE_ID

    def set_active_profile_id(self, version: str, profile_id: str) -> None:
        self.ensure_profiles_layout(version)
        write_active_profile_id(self.profiles_dir(version), profile_id)

    def _resolve_profile_id(self, version: str, profile_id: str | None) -> str:
        if profile_id:
            return profile_id
        return self.get_active_profile_id(version)

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

    def list_item_icons(self, version: str, profile_id: str | None = None) -> list[str]:
        icons: set[str] = set()
        rendered_dir = self._rendered_icons_dir(version, profile_id)

        for directory in (rendered_dir, self._legacy_textures_dir(version)):
            if directory is None:
                continue
            for path in directory.glob("*.png"):
                icons.add(path.name)

        # Пока renderer ещё не создал rendered-icons, даём манифест из рецептов
        # (с jar-fallback). После появления папки — только реальные PNG, даже если
        # папка пока пустая: иначе браузер запрашивает несуществующие плоские текстуры.
        if not icons and rendered_dir is None and self.resolve_jar_path(version) is not None:
            icons.update(self._recipe_icon_filenames(version))

        return sorted(icons)

    def icons_revision(self, version: str, profile_id: str | None = None) -> str:
        rendered_dir = self._rendered_icons_dir(version, profile_id)
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
        tags = {tag_id: registry.resolve_tag(tag_id) for tag_id in registry.list_tag_ids()}
        return {
            "version": version,
            "tags": tags,
            "aliases": registry.aliases,
        }

    def resolve_item_icon_path(
        self,
        version: str,
        filename: str,
        profile_id: str | None = None,
    ) -> Path | None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        texture_id = texture_id_from_icon_filename(safe_name)
        resolved_filename = f"{texture_id}.png"

        for directory in (
            self._rendered_icons_dir(version, profile_id),
            self._legacy_textures_dir(version),
        ):
            if directory is None:
                continue
            for candidate_name in {safe_name, resolved_filename}:
                candidate = directory / candidate_name
                if candidate.is_file():
                    return candidate

        from app.services.kubejs_assets import resolve_kubejs_item_icon_path

        kubejs_path = resolve_kubejs_item_icon_path(
            version,
            safe_name,
            profile_id=profile_id,
        )
        if kubejs_path is not None:
            return kubejs_path

        return None

    def resolve_item_icon(
        self,
        version: str,
        filename: str,
        profile_id: str | None = None,
    ) -> tuple[Literal["file", "bytes"], Path | bytes] | None:
        icon_path = self.resolve_item_icon_path(version, filename, profile_id=profile_id)
        if icon_path is not None:
            return ("file", icon_path)

        jar_bytes = self.read_jar_texture_bytes(version, filename)
        if jar_bytes is not None:
            return ("bytes", jar_bytes)

        mod_jar_bytes = self.read_mod_jar_texture_bytes(version, filename, profile_id=profile_id)
        if mod_jar_bytes is not None:
            return ("bytes", mod_jar_bytes)

        return None

    def read_mod_jar_texture_bytes(
        self,
        version: str,
        filename: str,
        profile_id: str | None = None,
    ) -> bytes | None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        icon_id = texture_id_from_icon_filename(safe_name)
        namespace_hint, texture_id = _mod_icon_id_parts(icon_id)
        mods_dir = self.mods_dir(version, profile_id)
        if not mods_dir.is_dir():
            return None

        jar_paths = sorted(mods_dir.glob("*.jar"))
        if namespace_hint:
            preferred = [
                jar_path
                for jar_path in jar_paths
                if namespace_hint.lower() in jar_path.name.lower()
            ]
            jar_paths = preferred + [
                jar_path for jar_path in jar_paths if jar_path not in preferred
            ]

        for jar_path in jar_paths:
            payload = self._read_texture_bytes_from_jar(jar_path, texture_id)
            if payload is not None:
                return payload
        return None

    def _read_texture_bytes_from_jar(self, jar_path: Path, icon_id: str) -> bytes | None:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for variant_id in _texture_id_variants(icon_id):
                    for entry in archive.namelist():
                        if not entry.endswith(f"/{variant_id}.png"):
                            continue
                        if "/textures/item/" in entry or "/textures/block/" in entry:
                            return archive.read(entry)
        except (OSError, zipfile.BadZipFile):
            return None
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

    def _to_renderer_path(self, host_path: Path) -> str:
        """Преобразует путь бэкенда в путь, видимый контейнеру renderer (общий volume)."""
        settings = get_settings()
        versions_root = settings.minecraft_versions_path.resolve()
        renderer_root = Path(settings.renderer_minecraft_root)
        resolved = host_path.resolve()
        if renderer_root.is_dir():
            try:
                relative = resolved.relative_to(versions_root)
                return str((renderer_root / relative).resolve())
            except ValueError:
                pass
        return str(resolved)

    def renderer_jar_path(self, version: str) -> str | None:
        local_jar = self.resolve_jar_path(version)
        if local_jar is None:
            return None
        return self._to_renderer_path(local_jar)

    def renderer_output_dir(self, version: str, profile_id: str | None = None) -> str:
        directory = self.ensure_rendered_icons_dir(version, profile_id)
        return self._to_renderer_path(directory)

    def renderer_mod_jar_paths(self, version: str, profile_id: str | None = None) -> list[str]:
        mods_dir = self.mods_dir(version, profile_id)
        if not mods_dir.is_dir():
            return []
        return [
            self._to_renderer_path(path)
            for path in sorted(mods_dir.glob("*.jar"))
            if path.is_file()
        ]

    def ensure_rendered_icons_dir(self, version: str, profile_id: str | None = None) -> Path:
        directory = (
            self.profile_dir(
                version,
                self._resolve_profile_id(version, profile_id),
            )
            / "rendered-icons"
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def profile_block_textures_dir(
        self,
        version: str,
        profile_id: str | None = None,
        *,
        create: bool = False,
    ) -> Path:
        directory = self.profile_dir(
            version,
            self._resolve_profile_id(version, profile_id),
        ) / "block-textures"
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _legacy_block_textures_dir(self, version: str) -> Path | None:
        directory = self._version_dir(version) / "block-textures"
        if directory.is_dir():
            return directory
        return None

    def resolve_block_texture_path(
        self,
        version: str,
        filename: str,
        profile_id: str | None = None,
    ) -> Path | None:
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".png"):
            return None

        for directory in (
            self.profile_block_textures_dir(version, profile_id),
            self._legacy_block_textures_dir(version),
        ):
            if directory is None or not directory.is_dir():
                continue
            candidate = directory / safe_name
            if candidate.is_file():
                return candidate
        return None

    def list_block_textures(self, version: str, profile_id: str | None = None) -> list[str]:
        names: set[str] = set()
        for directory in (
            self.profile_block_textures_dir(version, profile_id),
            self._legacy_block_textures_dir(version),
        ):
            if directory is None or not directory.is_dir():
                continue
            names.update(path.name for path in directory.glob("*.png"))
        return sorted(names)

    def list_rendered_icon_ids(self, version: str, profile_id: str | None = None) -> set[str]:
        directory = self._rendered_icons_dir(version, profile_id)
        if directory is None:
            return set()
        return {path.stem for path in directory.glob("*.png")}

    def _has_version_data(self, version: str) -> bool:
        return self.is_version_installed(version)

    def _version_dir(self, version: str) -> Path:
        return get_settings().minecraft_versions_path / version

    def _rendered_icons_dir(self, version: str, profile_id: str | None = None) -> Path | None:
        directory = (
            self.profile_dir(
                version,
                self._resolve_profile_id(version, profile_id),
            )
            / "rendered-icons"
        )
        if directory.is_dir():
            return directory
        legacy = self._version_dir(version) / "rendered-icons"
        if legacy.is_dir():
            return legacy
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
