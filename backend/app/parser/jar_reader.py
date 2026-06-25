from __future__ import annotations

import re
import tomllib
import zipfile
from pathlib import PurePosixPath

import orjson

from app.parser.exceptions import JarParseError
from app.parser.loaders import ModLoader
from app.parser.models import RawModData, RawModMeta, RawRecipeFile

RECIPE_PATH = re.compile(r"^data/([^/]+)/recipes?/(.+\.json)$")
ADVANCEMENT_SEGMENT = "/advancement/"


class JarReader:
    def read(self, jar_path: str) -> RawModData:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                meta = self._read_mod_meta(archive, jar_path)
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

    def _read_mod_meta(self, archive: zipfile.ZipFile, jar_path: str) -> RawModMeta:
        names = set(archive.namelist())
        if "META-INF/neoforge.mods.toml" in names:
            return self._read_mods_toml(
                archive.read("META-INF/neoforge.mods.toml"),
                loader=ModLoader.NEOFORGE,
            )
        if "fabric.mod.json" in names:
            return self._read_fabric_meta(archive.read("fabric.mod.json"))
        if "META-INF/mods.toml" in names:
            return self._read_mods_toml(
                archive.read("META-INF/mods.toml"),
                loader=ModLoader.FORGE,
            )
        if "mcmod.info" in names:
            return self._read_mcmod_info(archive.read("mcmod.info"))
        raise JarParseError(
            "Mod metadata not found (expected neoforge.mods.toml, fabric.mod.json, mods.toml, or mcmod.info)"
        )

    def _read_mods_toml(self, raw: bytes, *, loader: ModLoader) -> RawModMeta:
        data = tomllib.loads(raw.decode("utf-8"))
        mods = data.get("mods")
        if not mods:
            raise JarParseError("mods.toml has no [[mods]] section")
        first = mods[0]
        mod_id = first.get("modId")
        if not mod_id:
            raise JarParseError("mods.toml is missing modId")
        name = first.get("displayName") or mod_id
        minecraft_version_range = self._extract_minecraft_range(data, mod_id)
        return RawModMeta(
            mod_id=mod_id,
            name=name,
            loader=loader,
            minecraft_version_range=minecraft_version_range,
        )

    def _read_fabric_meta(self, raw: bytes) -> RawModMeta:
        data = orjson.loads(raw)
        mod_id = data.get("id")
        if not mod_id:
            raise JarParseError("fabric.mod.json is missing id")
        name = data.get("name") or mod_id
        depends = data.get("depends")
        minecraft_version_range = None
        if isinstance(depends, dict):
            minecraft_dep = depends.get("minecraft")
            if isinstance(minecraft_dep, str):
                minecraft_version_range = minecraft_dep
        return RawModMeta(
            mod_id=mod_id,
            name=name,
            loader=ModLoader.FABRIC,
            minecraft_version_range=minecraft_version_range,
        )

    def _read_mcmod_info(self, raw: bytes) -> RawModMeta:
        data = orjson.loads(raw)
        if not isinstance(data, list) or not data:
            raise JarParseError("mcmod.info must be a non-empty JSON array")
        first = data[0]
        if not isinstance(first, dict):
            raise JarParseError("mcmod.info entry must be an object")
        mod_id = first.get("modid")
        if not mod_id:
            raise JarParseError("mcmod.info is missing modid")
        name = first.get("name") or mod_id
        mcversion = first.get("mcversion")
        minecraft_version = mcversion if isinstance(mcversion, str) and mcversion else None
        return RawModMeta(
            mod_id=mod_id,
            name=name,
            loader=ModLoader.FORGE,
            minecraft_version=minecraft_version,
        )

    @staticmethod
    def _extract_minecraft_range(data: dict[str, object], mod_id: str) -> str | None:
        dependencies = data.get("dependencies")
        if not isinstance(dependencies, dict):
            return None

        groups: list[object] = []
        mod_entries = dependencies.get(mod_id)
        if isinstance(mod_entries, list):
            groups.append(mod_entries)
        groups.extend(entry for entry in dependencies.values() if isinstance(entry, list))

        for entries in groups:
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("modId") == "minecraft":
                    version_range = entry.get("versionRange")
                    if isinstance(version_range, str) and version_range.strip():
                        return version_range.strip()
        return None

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
