from __future__ import annotations

import tomllib
import zipfile
from pathlib import Path

import orjson

from app.parser.exceptions import JarParseError
from app.parser.jar_meta import guess_display_name_from_jar_filename, guess_mod_id_from_jar_filename
from app.parser.loaders import ModLoader
from app.parser.models import RawModData, RawModMeta, RawRecipeFile
from app.recipes.loaders.recipe_paths import discover_recipe_file, mod_jar_recipe_patterns


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
            try:
                return self._read_mcmod_info(archive.read("mcmod.info"))
            except (JarParseError, orjson.JSONDecodeError):
                pass
        mcmod_path = next(
            (name for name in names if name.lower().endswith("mcmod.info")),
            None,
        )
        if mcmod_path is not None:
            try:
                return self._read_mcmod_info(archive.read(mcmod_path))
            except (JarParseError, orjson.JSONDecodeError):
                pass
        return self._infer_meta_from_jar(archive, jar_path)

    def _infer_meta_from_jar(self, archive: zipfile.ZipFile, jar_path: str) -> RawModMeta:
        names = archive.namelist()
        if any(name.startswith("ic2classic/") for name in names):
            return RawModMeta(
                mod_id="ic2",
                name="IC2 Classic",
                loader=ModLoader.FORGE,
            )
        if any(name.startswith("ic2/") for name in names):
            return RawModMeta(
                mod_id="ic2",
                name="IndustrialCraft 2",
                loader=ModLoader.FORGE,
            )

        filename = Path(jar_path).name
        mod_id = guess_mod_id_from_jar_filename(filename)
        name = guess_display_name_from_jar_filename(filename, mod_id)
        return RawModMeta(
            mod_id=mod_id,
            name=name,
            loader=ModLoader.FORGE,
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
        entries: list[object]
        if isinstance(data, dict):
            if isinstance(data.get("modList"), list):
                entries = data["modList"]
            elif "modid" in data or "modId" in data:
                entries = [data]
            else:
                raise JarParseError("mcmod.info object is missing modid")
        elif isinstance(data, list):
            entries = data
        else:
            raise JarParseError("mcmod.info must be a JSON array or object")

        if not entries:
            raise JarParseError("mcmod.info must be a non-empty JSON array")
        first = entries[0]
        if not isinstance(first, dict):
            raise JarParseError("mcmod.info entry must be an object")
        mod_id = first.get("modid") or first.get("modId")
        if not mod_id:
            raise JarParseError("mcmod.info is missing modid")
        name = first.get("name") or mod_id
        mcversion = first.get("mcversion")
        minecraft_version = mcversion if isinstance(mcversion, str) and mcversion else None
        return RawModMeta(
            mod_id=str(mod_id),
            name=str(name),
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
        patterns = mod_jar_recipe_patterns()
        for entry in archive.namelist():
            if not any(pattern.match(entry) for pattern in patterns):
                continue

            discovered = discover_recipe_file(entry)
            if discovered is None:
                continue

            try:
                data = orjson.loads(archive.read(discovered.filename))
            except orjson.JSONDecodeError as exc:
                raise JarParseError(f"Invalid recipe JSON: {discovered.filename}") from exc
            if not isinstance(data, dict):
                raise JarParseError(f"Recipe root must be an object: {discovered.filename}")
            recipes.append(
                RawRecipeFile(
                    recipe_id=discovered.recipe_id,
                    namespace=discovered.namespace,
                    filename=discovered.filename,
                    data=data,
                )
            )
        return recipes
