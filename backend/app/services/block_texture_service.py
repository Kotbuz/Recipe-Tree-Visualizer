from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.services.version_service import version_service

# Префиксы внутри jar, где Minecraft/моды хранят описания состояний блоков, модели и текстуры.
_BLOCKSTATES_PREFIX = "blockstates/"
_MODELS_PREFIX = "models/"
_TEXTURES_PREFIX = "textures/"
_OUTPUT_DIR_NAME = "block-textures"
_MAX_PARENT_DEPTH = 8

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class BlockTextureResult:
    version: str
    block_types_total: int
    block_types_done: int
    textures_written: int
    already_present: int
    errors: list[str]


def _texture_ref_to_jar_entry(ref: str) -> tuple[str, str] | None:
    """`minecraft:block/stone` → ("minecraft", "assets/minecraft/textures/block/stone.png")."""
    if not ref or ref.startswith("#"):
        return None
    namespace, _, path = ref.partition(":")
    if not path:
        namespace, path = "minecraft", namespace
    path = path.strip("/")
    if not path:
        return None
    return namespace, f"assets/{namespace}/textures/{path}.png"


def _model_ref_to_jar_entry(ref: str) -> str | None:
    """`minecraft:block/stone` → `assets/minecraft/models/block/stone.json`."""
    if not ref:
        return None
    namespace, _, path = ref.partition(":")
    if not path:
        namespace, path = "minecraft", namespace
    path = path.strip("/")
    if not path:
        return None
    return f"assets/{namespace}/models/{path}.json"


def _output_filename(texture_ref: str) -> str:
    namespace, _, path = texture_ref.partition(":")
    if not path:
        namespace, path = "minecraft", namespace
    leaf = path.strip("/").removeprefix("block/")
    flat = leaf.replace("/", "_")
    return flat + ".png" if namespace == "minecraft" else f"{namespace}_{flat}.png"


class BlockTextureService:
    """Извлекает плоские PNG текстуры блоков из jar (не 3D-рендер, см. K2).

    Прогресс считается по типам блоков (blockstate), а не по файлам текстур —
    одному блоку соответствует несколько PNG (`_top`, `_side`…), см. X2.
    """

    def extract(
        self,
        version: str,
        *,
        profile_id: str | None = None,
        force: bool = False,
        progress_cb: ProgressCallback | None = None,
    ) -> BlockTextureResult:
        jar_paths = self._collect_jar_paths(version, profile_id=profile_id)
        if not jar_paths:
            return BlockTextureResult(
                version=version,
                block_types_total=0,
                block_types_done=0,
                textures_written=0,
                already_present=0,
                errors=["Нет jar-файлов для извлечения текстур блоков"],
            )

        output_dir = version_service.profile_dir(
            version,
            version_service._resolve_profile_id(version, profile_id),
        ) / _OUTPUT_DIR_NAME
        output_dir.mkdir(parents=True, exist_ok=True)
        existing = {path.name for path in output_dir.glob("*.png")}

        # Карта: тип блока (namespace:name) → jar, в котором он объявлен.
        block_types: dict[str, Path] = {}
        for jar_path in jar_paths:
            try:
                with zipfile.ZipFile(jar_path) as archive:
                    for entry in archive.namelist():
                        marker = f"/{_BLOCKSTATES_PREFIX}"
                        if marker not in entry or not entry.endswith(".json"):
                            continue
                        namespace = entry.split("assets/", 1)[-1].split("/", 1)[0]
                        name = entry.rsplit("/", 1)[-1].removesuffix(".json")
                        block_types.setdefault(f"{namespace}:{name}", jar_path)
            except (OSError, zipfile.BadZipFile) as exc:
                logger.warning("Cannot read blockstates from {}: {}", jar_path, exc)

        total = len(block_types)
        if progress_cb:
            progress_cb(0, total)

        archives: dict[Path, zipfile.ZipFile] = {}
        namelists: dict[Path, set[str]] = {}

        def get_archive(path: Path) -> zipfile.ZipFile | None:
            if path not in archives:
                try:
                    archive = zipfile.ZipFile(path)
                    archives[path] = archive
                    namelists[path] = set(archive.namelist())
                except (OSError, zipfile.BadZipFile) as exc:
                    logger.warning("Cannot open jar {}: {}", path, exc)
                    return None
            return archives[path]

        errors: list[str] = []
        written = 0
        already = 0
        done = 0
        try:
            for index, (block_type, owner_jar) in enumerate(sorted(block_types.items()), start=1):
                namespace, _, name = block_type.partition(":")
                texture_refs = self._resolve_block_textures(
                    namespace, name, owner_jar, jar_paths, get_archive, namelists
                )
                for ref in texture_refs:
                    target = _texture_ref_to_jar_entry(ref)
                    if target is None:
                        continue
                    _, entry_path = target
                    out_name = _output_filename(ref)
                    if out_name in existing and not force:
                        already += 1
                        continue
                    payload = self._read_entry(entry_path, jar_paths, get_archive, namelists)
                    if payload is None:
                        continue
                    (output_dir / out_name).write_bytes(payload)
                    existing.add(out_name)
                    written += 1
                done = index
                if progress_cb:
                    progress_cb(done, total)
        finally:
            for archive in archives.values():
                archive.close()

        logger.info(
            "Block textures for {}::{}: {} types, {} written, {} present",
            version,
            profile_id or "active",
            total,
            written,
            already,
        )
        return BlockTextureResult(
            version=version,
            block_types_total=total,
            block_types_done=done,
            textures_written=written,
            already_present=already,
            errors=errors,
        )

    def count_block_types(self, version: str, *, profile_id: str | None = None) -> int:
        jar_paths = self._collect_jar_paths(version, profile_id=profile_id)
        block_types: set[str] = set()
        for jar_path in jar_paths:
            try:
                with zipfile.ZipFile(jar_path) as archive:
                    for entry in archive.namelist():
                        if f"/{_BLOCKSTATES_PREFIX}" not in entry or not entry.endswith(".json"):
                            continue
                        namespace = entry.split("assets/", 1)[-1].split("/", 1)[0]
                        name = entry.rsplit("/", 1)[-1].removesuffix(".json")
                        block_types.add(f"{namespace}:{name}")
            except (OSError, zipfile.BadZipFile):
                continue
        return len(block_types)

    def _collect_jar_paths(self, version: str, *, profile_id: str | None) -> list[Path]:
        jars: list[Path] = []
        client_jar = version_service.resolve_jar_path(version)
        if client_jar is not None:
            jars.append(client_jar)
        mods_dir = version_service.mods_dir(version, profile_id)
        if mods_dir.is_dir():
            jars.extend(sorted(mods_dir.glob("*.jar")))
        return jars

    def _resolve_block_textures(
        self,
        namespace: str,
        name: str,
        owner_jar: Path,
        jar_paths: list[Path],
        get_archive,
        namelists: dict[Path, set[str]],
    ) -> set[str]:
        """blockstate → модели → текстуры. Возвращает множество texture refs."""
        blockstate_entry = f"assets/{namespace}/blockstates/{name}.json"
        data = self._read_json(blockstate_entry, jar_paths, get_archive, namelists)
        model_refs: set[str] = set()
        if isinstance(data, dict):
            self._collect_model_refs(data, model_refs)
        if not model_refs:
            # запасной путь — модель блока по имени
            model_refs.add(f"{namespace}:block/{name}")

        textures: set[str] = set()
        for model_ref in model_refs:
            self._collect_model_textures(
                model_ref, jar_paths, get_archive, namelists, textures, depth=0
            )
        return textures

    def _collect_model_refs(self, blockstate: dict, sink: set[str]) -> None:
        variants = blockstate.get("variants")
        if isinstance(variants, dict):
            for value in variants.values():
                entries = value if isinstance(value, list) else [value]
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("model"), str):
                        sink.add(entry["model"])
        multipart = blockstate.get("multipart")
        if isinstance(multipart, list):
            for part in multipart:
                if not isinstance(part, dict):
                    continue
                apply = part.get("apply")
                entries = apply if isinstance(apply, list) else [apply]
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("model"), str):
                        sink.add(entry["model"])

    def _collect_model_textures(
        self,
        model_ref: str,
        jar_paths: list[Path],
        get_archive,
        namelists: dict[Path, set[str]],
        sink: set[str],
        *,
        depth: int,
    ) -> None:
        if depth > _MAX_PARENT_DEPTH:
            return
        entry = _model_ref_to_jar_entry(model_ref)
        if entry is None:
            return
        data = self._read_json(entry, jar_paths, get_archive, namelists)
        if not isinstance(data, dict):
            return
        textures = data.get("textures")
        if isinstance(textures, dict):
            for value in textures.values():
                if isinstance(value, str) and not value.startswith("#"):
                    sink.add(value)
        parent = data.get("parent")
        if isinstance(parent, str) and "builtin/" not in parent:
            self._collect_model_textures(
                parent, jar_paths, get_archive, namelists, sink, depth=depth + 1
            )

    def _read_entry(
        self,
        entry_path: str,
        jar_paths: list[Path],
        get_archive,
        namelists: dict[Path, set[str]],
    ) -> bytes | None:
        for jar_path in jar_paths:
            archive = get_archive(jar_path)
            if archive is None:
                continue
            if entry_path in namelists.get(jar_path, ()):
                try:
                    return archive.read(entry_path)
                except (KeyError, OSError, zipfile.BadZipFile):
                    continue
        return None

    def _read_json(
        self,
        entry_path: str,
        jar_paths: list[Path],
        get_archive,
        namelists: dict[Path, set[str]],
    ) -> dict | None:
        payload = self._read_entry(entry_path, jar_paths, get_archive, namelists)
        if payload is None:
            return None
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None


block_texture_service = BlockTextureService()
