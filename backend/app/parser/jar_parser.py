from app.parser.jar_reader import JarReader
from app.parser.models import RawModData


class JarParser:
    def __init__(self, jar_reader: JarReader | None = None) -> None:
        self._jar_reader = jar_reader or JarReader()

    def extract(self, jar_path: str) -> RawModData:
        return self._jar_reader.read(jar_path)
