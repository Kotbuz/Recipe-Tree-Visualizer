from app.indexer.mod_registry import ModRegistry, registry
from app.parser.jar_parser import JarParser
from app.schemas.domain import ModSummary


class ModService:
    def __init__(self, mod_registry: ModRegistry, jar_parser: JarParser) -> None:
        self._registry = mod_registry
        self._jar_parser = jar_parser

    def list_mods(self) -> list[ModSummary]:
        return self._registry.list_mods()

    def upload_mods(self, jar_paths: list[str]) -> list[ModSummary]:
        for jar_path in jar_paths:
            self._jar_parser.extract(jar_path)
        raise NotImplementedError("Mod upload pipeline is not implemented yet")

    def upload_modpack(self, archive_path: str) -> list[ModSummary]:
        raise NotImplementedError("Modpack import is not implemented yet")


mod_service = ModService(registry, JarParser())
