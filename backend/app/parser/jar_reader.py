import re
import tomllib
import zipfile
from pathlib import PurePosixPath

import orjson

from app.parser.exceptions import JarParseError
from app.parser.models import RawModData, RawModMeta, RawRecipeFile

RECIPE_PATH = re.compile(r"^data/([^/]+)/recipes?/(.+\.json)$")
ADVANCEMENT_SEGMENT = "/advancement/"


class JarReader:
    def read(self, jar_path: str) -> RawModData:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                meta = self._read_mod_meta(archive)
                recipe_files = self._discover_recipes(archive)
                texture_paths = [
                    name
                    for name in archive.namelist()
                    if name.startswith(f"assets/{meta.mod_id}/textures/") and name.endswith(".png")
                ]
                return RawModData(
                    meta=meta,
                    jar_path=jar_path,
                    recipe_files=recipe_files,
                    texture_paths=texture_paths,
                )
        except zipfile.BadZipFile as exc:
            raise JarParseError(f"Invalid jar archive: {jar_path}") from exc

    def _read_mod_meta(self, archive: zipfile.ZipFile) -> RawModMeta:
        if "META-INF/neoforge.mods.toml" in archive.namelist():
            return self._read_neoforge_meta(archive.read("META-INF/neoforge.mods.toml"))
        if "fabric.mod.json" in archive.namelist():
            return self._read_fabric_meta(archive.read("fabric.mod.json"))
        raise JarParseError(
            "Mod metadata not found (expected neoforge.mods.toml or fabric.mod.json)"
        )

    def _read_neoforge_meta(self, raw: bytes) -> RawModMeta:
        data = tomllib.loads(raw.decode("utf-8"))
        mods = data.get("mods")
        if not mods:
            raise JarParseError("neoforge.mods.toml has no [[mods]] section")
        first = mods[0]
        mod_id = first.get("modId")
        if not mod_id:
            raise JarParseError("neoforge.mods.toml is missing modId")
        name = first.get("displayName") or mod_id
        return RawModMeta(mod_id=mod_id, name=name)

    def _read_fabric_meta(self, raw: bytes) -> RawModMeta:
        data = orjson.loads(raw)
        mod_id = data.get("id")
        if not mod_id:
            raise JarParseError("fabric.mod.json is missing id")
        name = data.get("name") or mod_id
        return RawModMeta(mod_id=mod_id, name=name)

    def _discover_recipes(self, archive: zipfile.ZipFile) -> list[RawRecipeFile]:
        recipes: list[RawRecipeFile] = []
        for entry in archive.namelist():
            if ADVANCEMENT_SEGMENT in entry:
                continue
            match = RECIPE_PATH.match(entry)
            if not match:
                continue
            namespace, relative_path = match.groups()
            recipe_name = PurePosixPath(relative_path).stem
            recipe_id = f"{namespace}:{recipe_name}"
            try:
                data = orjson.loads(archive.read(entry))
            except orjson.JSONDecodeError as exc:
                raise JarParseError(f"Invalid recipe JSON: {entry}") from exc
            if not isinstance(data, dict):
                raise JarParseError(f"Recipe root must be an object: {entry}")
            recipes.append(
                RawRecipeFile(
                    recipe_id=recipe_id,
                    namespace=namespace,
                    filename=entry,
                    data=data,
                )
            )
        return recipes
