from app.indexer.mod_indexer import ModIndexer
from app.indexer.mod_registry import ModIndex
from app.parser.jar_reader import JarReader
from app.parser.models import RawModData


class JarParser:
    def __init__(
        self,
        jar_reader: JarReader | None = None,
        mod_indexer: ModIndexer | None = None,
    ) -> None:
        self._jar_reader = jar_reader or JarReader()
        self._mod_indexer = mod_indexer or ModIndexer()

    def extract(self, jar_path: str) -> RawModData:
        return self._jar_reader.read(jar_path)

    def parse_mod(self, jar_path: str) -> ModIndex:
        raw = self.extract(jar_path)
        return self._mod_indexer.build(raw)
