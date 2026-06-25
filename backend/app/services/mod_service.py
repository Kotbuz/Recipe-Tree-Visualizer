from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.indexer.mod_registry import ModRegistry, registry
from app.indexer.mod_summary import build_mod_summary
from app.parser.jar_reader import JarReader
from app.recipes.manager import recipe_manager
from app.schemas.domain import ModSummary


class ModService:
    def __init__(self, mod_registry: ModRegistry, jar_reader: JarReader | None = None) -> None:
        self._registry = mod_registry
        self._jar_reader = jar_reader or JarReader()
        self._settings = get_settings()

    def list_mods(self) -> list[ModSummary]:
        return self._registry.list_mods()

    async def upload_mods(self, files: list[UploadFile]) -> list[ModSummary]:
        storage_dir = Path(self._settings.mods_storage_dir)
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

    def _register_jar(self, jar_path: str) -> ModSummary:
        raw = self._jar_reader.read(jar_path)
        result = recipe_manager.load_mod_jar(jar_path)
        summary = build_mod_summary(raw, result)
        return self._registry.register_summary(summary)


mod_service = ModService(registry, JarReader())
