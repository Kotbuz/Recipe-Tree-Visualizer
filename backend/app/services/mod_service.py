from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from loguru import logger

from app.core.config import get_settings
from app.indexer.mod_registry import ModRegistry, registry
from app.indexer.mod_summary import build_mod_summary
from app.parser.exceptions import JarParseError
from app.parser.jar_reader import JarReader
from app.parser.minecraft_version import mod_supports_game_version
from app.recipes.manager import recipe_manager
from app.schemas.domain import ModSummary


class ModService:
    def __init__(self, mod_registry: ModRegistry, jar_reader: JarReader | None = None) -> None:
        self._registry = mod_registry
        self._jar_reader = jar_reader or JarReader()
        self._settings = get_settings()

    def list_mods(self, game_version: str | None = None) -> list[ModSummary]:
        mods = self._registry.list_mods()
        if game_version is None:
            return mods
        return [self._with_compatibility(mod, game_version) for mod in mods]

    def scan_storage_mods(self) -> list[ModSummary]:
        storage_dir = self._mods_storage_path()
        if not storage_dir.is_dir():
            return []

        summaries: list[ModSummary] = []
        for jar_path in sorted(storage_dir.glob("*.jar")):
            try:
                summaries.append(self._register_jar(str(jar_path)))
            except JarParseError as exc:
                logger.warning("Skipping mod jar {}: {}", jar_path.name, exc)
            except Exception:
                logger.exception("Failed to load mod jar {}", jar_path.name)
        return summaries

    async def upload_mods(self, files: list[UploadFile]) -> list[ModSummary]:
        storage_dir = self._mods_storage_path()
        storage_dir.mkdir(parents=True, exist_ok=True)

        summaries: list[ModSummary] = []
        for file in files:
            filename = file.filename or "mod.jar"
            destination = storage_dir / filename
            destination.write_bytes(await file.read())
            summaries.append(self._register_jar(str(destination)))
        return summaries

    def upload_mods_from_paths(self, jar_paths: list[str]) -> list[ModSummary]:
        return [self._register_jar(jar_path) for jar_path in jar_paths]

    def upload_modpack(self, archive_path: str) -> list[ModSummary]:
        raise NotImplementedError("Modpack import is not implemented yet")

    def _mods_storage_path(self) -> Path:
        storage_dir = Path(self._settings.mods_storage_dir)
        if storage_dir.is_absolute():
            return storage_dir
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / storage_dir).resolve()

    def _register_jar(self, jar_path: str) -> ModSummary:
        raw = self._jar_reader.read(jar_path)
        result = recipe_manager.load_mod_jar(jar_path, meta=raw.meta)
        summary = build_mod_summary(raw, result)
        return self._registry.register_summary(summary)

    def _with_compatibility(self, summary: ModSummary, game_version: str) -> ModSummary:
        compatible = mod_supports_game_version(
            minecraft_version=summary.minecraft_version,
            minecraft_version_range=summary.minecraft_version_range,
            jar_path=summary.jar_filename or summary.mod_id,
            game_version=game_version,
        )
        return summary.model_copy(update={"compatible": compatible})


mod_service = ModService(registry, JarReader())
