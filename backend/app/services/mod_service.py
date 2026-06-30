from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile
from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version
from app.indexer.mod_registry import ModRegistry, registry
from app.indexer.mod_summary import build_mod_summary
from app.parser.exceptions import JarParseError
from app.parser.jar_meta import guess_display_name_from_jar_filename, guess_mod_id_from_jar_filename
from app.parser.jar_reader import JarReader
from app.parser.loaders import ModLoader
from app.parser.minecraft_version import mod_supports_game_version
from app.recipes.manager import recipe_manager
from app.schemas.domain import ModSummary
from app.services.jvm_recipe_export_service import JvmRecipeExportError
from app.services.profile_storage import profile_storage_key
from app.services.version_service import version_service


class ModProfileNotFoundError(Exception):
    def __init__(self, version: str, profile_id: str) -> None:
        super().__init__(f"Profile not found: {version}/{profile_id}")
        self.version = version
        self.profile_id = profile_id


class ModVersionNotInstalledError(Exception):
    def __init__(self, version: str) -> None:
        super().__init__(f"Minecraft version is not installed: {version}")
        self.version = version


class ModNotFoundError(Exception):
    def __init__(self, jar_filename: str) -> None:
        super().__init__(f"Mod jar not found: {jar_filename}")
        self.jar_filename = jar_filename


class ModUploadTooLargeError(Exception):
    def __init__(self, filename: str, size_bytes: int, max_bytes: int) -> None:
        size_mb = size_bytes / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        super().__init__(
            f"Файл {filename} слишком большой ({size_mb:.1f} МБ, лимит {max_mb:.0f} МБ)"
        )
        self.filename = filename
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class ModService:
    def __init__(self, mod_registry: ModRegistry, jar_reader: JarReader | None = None) -> None:
        self._registry = mod_registry
        self._jar_reader = jar_reader or JarReader()
        self._loaded_versions: set[str] = set()

    def _resolve_profile_id(self, version: str, profile_id: str | None) -> str:
        return version_service._resolve_profile_id(version, profile_id)

    def _storage_key(self, version: str, profile_id: str | None = None) -> str:
        resolved = self._resolve_profile_id(version, profile_id)
        return profile_storage_key(version, resolved)

    def ensure_version_mods_loaded(
        self,
        version: str,
        profile_id: str | None = None,
    ) -> None:
        storage_key = self._storage_key(version, profile_id)
        if storage_key in self._loaded_versions:
            return
        if not version_service.is_version_installed(version):
            return
        self.scan_storage_mods(version, profile_id=profile_id, enrich_recipes=False)

    def list_mods(
        self,
        game_version: str | None = None,
        profile_id: str | None = None,
    ) -> list[ModSummary]:
        if not game_version:
            return []

        self.ensure_version_mods_loaded(game_version, profile_id=profile_id)
        storage_key = self._storage_key(game_version, profile_id)
        mods = self._registry.list_mods(storage_key)
        return [self._with_compatibility(mod, game_version) for mod in mods]

    def scan_storage_mods(
        self,
        version: str,
        profile_id: str | None = None,
        *,
        enrich_recipes: bool = True,
    ) -> list[ModSummary]:
        if not version_service.is_version_installed(version):
            return []

        version_service.ensure_profiles_layout(version)
        resolved_profile = self._resolve_profile_id(version, profile_id)
        storage_key = profile_storage_key(version, resolved_profile)

        recipe_manager.clear_mods_for_version(storage_key)
        self._registry.clear_version(storage_key)

        mods_dir = version_service.mods_dir(version, resolved_profile)
        if not mods_dir.is_dir():
            self._loaded_versions.add(storage_key)
            return []

        summaries: list[ModSummary] = []
        for jar_path in sorted(mods_dir.rglob("*.jar")):
            try:
                summaries.append(
                    self._register_jar_resilient(
                        str(jar_path),
                        version,
                        storage_key,
                        clear_recipe_caches=False,
                    )
                )
            except Exception:
                logger.exception("Failed to load mod jar {}", jar_path.name)

        recipe_manager._clear_caches()
        self._loaded_versions.add(storage_key)
        try:
            recipe_manager.get_recipe_bundle(version, profile_id=resolved_profile)
        except Exception:
            logger.exception(
                "Failed to warm recipe index for {} profile {}",
                version,
                resolved_profile,
            )
        if enrich_recipes:
            enriched = self._enrich_jvm_mod_summaries(version, resolved_profile, summaries)
        else:
            enriched = summaries
        for summary in enriched:
            self._registry.register_summary(storage_key, summary)
        return enriched

    def _enrich_jvm_mod_summaries(
        self,
        version: str,
        profile_id: str,
        summaries: list[ModSummary],
    ) -> list[ModSummary]:
        if recipe_layout_for_version(version) != "jvm" or not summaries:
            return summaries

        recipe_manager._clear_caches()
        try:
            recipes_by_mod: dict[str, list] = {}
            for recipe in recipe_manager.get_version_recipes(version, profile_id=profile_id):
                mod_id = recipe.mod_id
                if not mod_id:
                    continue
                recipes_by_mod.setdefault(mod_id, []).append(recipe)
        except JvmRecipeExportError as exc:
            logger.warning(
                "Recipe enrichment skipped for {} profile {}: {}",
                version,
                profile_id,
                exc,
            )
            return summaries

        enriched: list[ModSummary] = []
        for summary in summaries:
            mod_recipes = recipes_by_mod.get(summary.mod_id, [])
            if not mod_recipes:
                enriched.append(summary)
                continue

            item_ids: set[str] = set()
            for recipe in mod_recipes:
                for part in [*recipe.inputs, *recipe.outputs]:
                    item_ids.add(part.item_id)

            enriched.append(
                summary.model_copy(
                    update={
                        "recipe_count": len(mod_recipes),
                        "item_count": len(item_ids),
                    }
                )
            )
        return enriched

    async def upload_mods(
        self,
        files: list[UploadFile],
        version: str,
        profile_id: str | None = None,
    ) -> list[ModSummary]:
        resolved_profile = self._require_profile(version, profile_id)
        mods_dir = version_service.mods_dir(version, resolved_profile)
        max_bytes = get_settings().mod_upload_max_bytes
        storage_key = profile_storage_key(version, resolved_profile)

        summaries: list[ModSummary] = []
        for file in files:
            filename = file.filename or "mod.jar"
            content = await file.read()
            if len(content) > max_bytes:
                raise ModUploadTooLargeError(filename, len(content), max_bytes)

            destination = mods_dir / filename
            destination.write_bytes(content)
            summaries.append(self._register_jar_resilient(str(destination), version, storage_key))
        return summaries

    def upload_mods_from_paths(
        self,
        jar_paths: list[str],
        version: str,
        profile_id: str | None = None,
    ) -> list[ModSummary]:
        resolved_profile = self._require_profile(version, profile_id)
        mods_dir = version_service.mods_dir(version, resolved_profile)
        storage_key = profile_storage_key(version, resolved_profile)
        summaries: list[ModSummary] = []
        for jar_path in jar_paths:
            source = Path(jar_path)
            destination = mods_dir / source.name
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            summaries.append(self._register_jar_resilient(str(destination), version, storage_key))
        return summaries

    def upload_modpack(self, archive_path: str) -> list[ModSummary]:
        raise NotImplementedError("Modpack import is not implemented yet")

    def clear_loaded_state(self) -> None:
        self._loaded_versions.clear()

    def force_reload_version(
        self,
        version: str,
        profile_id: str | None = None,
        *,
        enrich_recipes: bool = True,
    ) -> list[ModSummary]:
        resolved_profile = self._require_profile(version, profile_id)
        storage_key = profile_storage_key(version, resolved_profile)
        self._loaded_versions.discard(storage_key)
        recipe_manager._clear_caches()
        return self.scan_storage_mods(
            version,
            profile_id=resolved_profile,
            enrich_recipes=enrich_recipes,
        )

    def delete_mod_jar(
        self,
        version: str,
        jar_filename: str,
        profile_id: str | None = None,
    ) -> list[ModSummary]:
        resolved_profile = self._require_profile(version, profile_id)
        safe_name = Path(jar_filename).name
        if not safe_name or safe_name != jar_filename.strip():
            raise ModNotFoundError(jar_filename)
        if not safe_name.lower().endswith(".jar"):
            raise ModNotFoundError(jar_filename)

        jar_path = version_service.mods_dir(version, resolved_profile) / safe_name
        if not jar_path.is_file():
            raise ModNotFoundError(safe_name)

        jar_path.unlink()
        logger.info(
            "Deleted mod jar {} for version {} profile {}",
            safe_name,
            version,
            resolved_profile,
        )
        return self.force_reload_version(version, profile_id=resolved_profile)

    def _require_profile(self, version: str, profile_id: str | None) -> str:
        self._require_installed_version(version)
        resolved = self._resolve_profile_id(version, profile_id)
        profile_dir = version_service.profile_dir(version, resolved)
        if not profile_dir.is_dir():
            raise ModProfileNotFoundError(version, resolved)
        return resolved

    def _require_installed_version(self, version: str) -> None:
        normalized = version.strip()
        if not normalized or not version_service.is_version_installed(normalized):
            raise ModVersionNotInstalledError(normalized or version)
        version_service.ensure_profiles_layout(normalized)

    def _register_jar(
        self,
        jar_path: str,
        version: str,
        storage_key: str,
        *,
        clear_recipe_caches: bool = True,
    ) -> ModSummary:
        raw = self._jar_reader.read(jar_path)
        result = recipe_manager.load_mod_jar(
            jar_path,
            meta=raw.meta,
            storage_version=storage_key,
            clear_caches=clear_recipe_caches,
        )
        summary = build_mod_summary(raw, result)
        return self._registry.register_summary(storage_key, summary)

    def _register_jar_resilient(
        self,
        jar_path: str,
        version: str,
        storage_key: str,
        *,
        clear_recipe_caches: bool = True,
    ) -> ModSummary:
        try:
            return self._register_jar(
                jar_path,
                version,
                storage_key,
                clear_recipe_caches=clear_recipe_caches,
            )
        except JarParseError as exc:
            logger.warning("Using fallback metadata for {}: {}", Path(jar_path).name, exc)
            return self._register_fallback_jar(jar_path, storage_key)

    def _register_fallback_jar(self, jar_path: str, storage_key: str) -> ModSummary:
        filename = Path(jar_path).name
        mod_id = guess_mod_id_from_jar_filename(filename)
        name = guess_display_name_from_jar_filename(filename, mod_id)
        summary = ModSummary(
            mod_id=mod_id,
            name=name,
            loader=ModLoader.FORGE.value,
            jar_filename=filename,
            item_count=0,
            recipe_count=0,
            machine_count=0,
            skipped_recipe_count=0,
        )
        return self._registry.register_summary(storage_key, summary)

    def _with_compatibility(self, summary: ModSummary, game_version: str) -> ModSummary:
        compatible = mod_supports_game_version(
            minecraft_version=summary.minecraft_version,
            minecraft_version_range=summary.minecraft_version_range,
            jar_path=summary.jar_filename or summary.mod_id,
            game_version=game_version,
        )
        return summary.model_copy(update={"compatible": compatible})


mod_service = ModService(registry, JarReader())
