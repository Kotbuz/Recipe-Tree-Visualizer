from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.indexer.mod_indexer import ModIndexer
from app.indexer.mod_registry import ModRegistry, registry
from app.parser.jar_parser import JarParser
from app.parser.jar_reader import JarReader
from app.schemas.domain import ModSummary


class ModService:
    def __init__(self, mod_registry: ModRegistry, jar_parser: JarParser) -> None:
        self._registry = mod_registry
        self._jar_parser = jar_parser
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
            index = self._jar_parser.parse_mod(str(destination))
            summaries.append(self._registry.register(index))
        return summaries

    def upload_mods_from_paths(self, jar_paths: list[str]) -> list[ModSummary]:
        summaries: list[ModSummary] = []
        for jar_path in jar_paths:
            index = self._jar_parser.parse_mod(jar_path)
            summaries.append(self._registry.register(index))
        return summaries

    def upload_modpack(self, archive_path: str) -> list[ModSummary]:
        raise NotImplementedError("Modpack import is not implemented yet")


mod_service = ModService(
    registry,
    JarParser(jar_reader=JarReader(), mod_indexer=ModIndexer()),
)
