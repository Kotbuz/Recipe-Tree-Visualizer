from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

from app.recipes.ingredients import create_ingredient_resolver
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import Recipe
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe
from app.recipes.models import ProviderResult
from app.services.version_service import version_service

SNAPSHOT_FORMAT_VERSION = 1
BAKE_DIR_NAME = "bake"
RECIPES_FILENAME = "recipes.baked.json"
META_FILENAME = "bake_meta.json"
LOG_FILENAME = "bake.log"
PARTIAL_META_FILENAME = "bake_meta.partial.json"


class RecipeSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecipeSnapshotMeta:
    format_version: int
    minecraft_version: str
    loader: str | None
    loader_version: str | None
    exported_at: str
    recipe_count: int
    item_count: int = 0
    instance_path: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class RecipeSnapshotStatus:
    has_snapshot: bool
    meta: RecipeSnapshotMeta | None
    recipe_count: int
    last_error: str | None
    item_count: int = 0


def count_snapshot_items(snapshot_payload: dict[str, Any]) -> int:
    """Уникальные item_id среди inputs+outputs всех рецептов снимка (для статуса «Mп»)."""
    recipes_obj = snapshot_payload.get("recipes")
    if not isinstance(recipes_obj, dict):
        return 0
    item_ids: set[str] = set()
    for recipe_data in recipes_obj.values():
        if not isinstance(recipe_data, dict):
            continue
        for key in ("inputs", "outputs", "results", "ingredients"):
            section = recipe_data.get(key)
            if isinstance(section, list):
                _collect_item_ids(section, item_ids)
    return len(item_ids)


def _collect_item_ids(section: list[Any], sink: set[str]) -> None:
    for part in section:
        if isinstance(part, str):
            sink.add(part)
        elif isinstance(part, dict):
            for id_key in ("item", "item_id", "id", "fluid"):
                value = part.get(id_key)
                if isinstance(value, str) and value:
                    sink.add(value)
                    break


def bake_dir(version: str, profile_id: str) -> Path:
    return version_service.profile_dir(version, profile_id) / BAKE_DIR_NAME


def recipes_snapshot_path(version: str, profile_id: str) -> Path:
    return bake_dir(version, profile_id) / RECIPES_FILENAME


def bake_meta_path(version: str, profile_id: str) -> Path:
    return bake_dir(version, profile_id) / META_FILENAME


def bake_log_path(version: str, profile_id: str) -> Path:
    return bake_dir(version, profile_id) / LOG_FILENAME


def ensure_bake_dir(version: str, profile_id: str) -> Path:
    path = bake_dir(version, profile_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_bake_log(version: str, profile_id: str, text: str) -> None:
    path = ensure_bake_dir(version, profile_id) / LOG_FILENAME
    path.write_text(text, encoding="utf-8")


def append_bake_log(version: str, profile_id: str, text: str) -> None:
    path = ensure_bake_dir(version, profile_id) / LOG_FILENAME
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def record_bake_failure(
    version: str,
    profile_id: str,
    *,
    error: str,
    log_tail: str | None = None,
) -> None:
    directory = ensure_bake_dir(version, profile_id)
    partial_path = directory / PARTIAL_META_FILENAME
    payload: dict[str, Any] = {
        "failed_at": datetime.now(UTC).isoformat(),
        "error": error.strip(),
    }
    if log_tail:
        payload["log_tail"] = log_tail[-8000:]
    partial_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if log_tail:
        write_bake_log(version, profile_id, log_tail)


def _parse_meta(payload: dict[str, Any]) -> RecipeSnapshotMeta:
    return RecipeSnapshotMeta(
        format_version=int(payload.get("format_version", 0)),
        minecraft_version=str(payload.get("minecraft_version", "")),
        loader=payload.get("loader") if isinstance(payload.get("loader"), str) else None,
        loader_version=(
            payload.get("loader_version")
            if isinstance(payload.get("loader_version"), str)
            else None
        ),
        exported_at=str(payload.get("exported_at", "")),
        recipe_count=int(payload.get("recipe_count", 0)),
        item_count=int(payload.get("item_count", 0)),
        instance_path=(
            payload.get("instance_path")
            if isinstance(payload.get("instance_path"), str)
            else None
        ),
        last_error=(
            payload.get("last_error") if isinstance(payload.get("last_error"), str) else None
        ),
    )


def read_snapshot_status(version: str, profile_id: str) -> RecipeSnapshotStatus:
    meta_path = bake_meta_path(version, profile_id)
    partial_path = bake_dir(version, profile_id) / PARTIAL_META_FILENAME
    last_error: str | None = None
    if partial_path.is_file():
        try:
            partial = json.loads(partial_path.read_text(encoding="utf-8"))
            if isinstance(partial, dict) and isinstance(partial.get("error"), str):
                last_error = partial["error"]
        except json.JSONDecodeError:
            pass

    if not meta_path.is_file():
        return RecipeSnapshotStatus(has_snapshot=False, meta=None, recipe_count=0, last_error=last_error)

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return RecipeSnapshotStatus(
            has_snapshot=False,
            meta=None,
            recipe_count=0,
            last_error=f"Повреждён bake_meta.json: {exc}",
        )

    if not isinstance(payload, dict):
        return RecipeSnapshotStatus(
            has_snapshot=False,
            meta=None,
            recipe_count=0,
            last_error="Некорректный bake_meta.json",
        )

    meta = _parse_meta(payload)
    snapshot_path = recipes_snapshot_path(version, profile_id)
    has_snapshot = snapshot_path.is_file()
    return RecipeSnapshotStatus(
        has_snapshot=has_snapshot,
        meta=meta,
        recipe_count=meta.recipe_count if has_snapshot else 0,
        item_count=meta.item_count if has_snapshot else 0,
        last_error=last_error or meta.last_error,
    )


def commit_snapshot(
    version: str,
    profile_id: str,
    *,
    snapshot_payload: dict[str, Any],
    meta: dict[str, Any],
    log_text: str | None = None,
) -> int:
    directory = ensure_bake_dir(version, profile_id)
    temp_recipes = directory / f".{RECIPES_FILENAME}.tmp"
    temp_meta = directory / f".{META_FILENAME}.tmp"

    recipes_blob = json.dumps(snapshot_payload, ensure_ascii=False, separators=(",", ":"))
    temp_recipes.write_text(recipes_blob, encoding="utf-8")
    temp_meta.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    shutil.move(str(temp_recipes), str(directory / RECIPES_FILENAME))
    shutil.move(str(temp_meta), str(directory / META_FILENAME))
    (directory / PARTIAL_META_FILENAME).unlink(missing_ok=True)
    if log_text:
        write_bake_log(version, profile_id, log_text)

    recipe_count = int(meta.get("recipe_count", 0))
    logger.info(
        "Committed recipe snapshot for {}::{} ({} recipes)",
        version,
        profile_id,
        recipe_count,
    )
    return recipe_count


@lru_cache(maxsize=16)
def _load_snapshot_recipes_cached(
    snapshot_path: str,
    meta_mtime_ns: int,
) -> tuple[Recipe, ...]:
    path = Path(snapshot_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RecipeSnapshotError("recipes.baked.json must be a JSON object")

    recipes_obj = payload.get("recipes")
    if not isinstance(recipes_obj, dict):
        raise RecipeSnapshotError("recipes.baked.json missing recipes object")

    minecraft_version = str(payload.get("minecraft_version", ""))
    tag_loader = TagLoader()
    resolver = create_ingredient_resolver(minecraft_version)
    parser = JsonRecipeParser(resolver=resolver)
    source = f"bake:{path.parent.parent.name}"

    merged: list[Recipe] = []
    for recipe_id, recipe_data in recipes_obj.items():
        if not isinstance(recipe_id, str) or not isinstance(recipe_data, dict):
            continue
        mod_id = recipe_id.split(":", 1)[0] if ":" in recipe_id else None
        provider_result = ProviderResult()
        try_add_recipe(
            parser,
            provider_result,
            recipe_id,
            recipe_data,
            source=source,
            mod_id=mod_id,
        )
        merged.extend(provider_result.recipes)

    return tuple(merged)


def load_snapshot_recipes(version: str, profile_id: str) -> tuple[Recipe, ...] | None:
    snapshot_path = recipes_snapshot_path(version, profile_id)
    meta_path = bake_meta_path(version, profile_id)
    if not snapshot_path.is_file() or not meta_path.is_file():
        return None

    try:
        return _load_snapshot_recipes_cached(
            str(snapshot_path.resolve()),
            meta_path.stat().st_mtime_ns,
        )
    except Exception as exc:
        logger.warning(
            "Failed to load baked recipes for {}::{}: {}",
            version,
            profile_id,
            exc,
        )
        return None


def clear_snapshot_cache() -> None:
    _load_snapshot_recipes_cached.cache_clear()
