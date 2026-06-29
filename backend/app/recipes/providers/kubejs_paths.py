from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from app.recipes.models import SkippedRecipe


def iter_kubejs_recipe_files(kubejs_dir: Path) -> list[tuple[str, Path]]:
    data_dir = kubejs_dir / "data"
    if not data_dir.is_dir():
        return []

    discovered: list[tuple[str, Path]] = []
    for file_path in sorted(data_dir.rglob("*.json")):
        if not file_path.is_file():
            continue
        relative = PurePosixPath(*file_path.relative_to(data_dir).parts)
        recipe_id = recipe_id_from_data_relative(relative)
        if recipe_id is None:
            continue
        discovered.append((recipe_id, file_path))
    return discovered


def recipe_id_from_data_relative(relative: PurePosixPath) -> str | None:
    parts = relative.parts
    if "recipe" not in parts or len(parts) < 3:
        return None
    recipe_idx = parts.index("recipe")
    if recipe_idx < 1:
        return None
    namespace = parts[0]
    suffix = "/".join(parts[recipe_idx + 1 :])
    if suffix.endswith(".json"):
        suffix = suffix[: -len(".json")]
    if not suffix:
        return None
    return f"{namespace}:{suffix}"


def is_kubejs_recipe_enabled(data: dict[str, object]) -> bool:
    for key in ("neoforge:conditions", "conditions", "fabric:load_conditions"):
        conditions = data.get(key)
        if not isinstance(conditions, list):
            continue
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            condition_type = condition.get("type")
            if condition_type in {"neoforge:false", "forge:false", "minecraft:false"}:
                return False
    return True


def load_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def skipped_recipe(recipe_id: str, raw_type: str | None, reason: str) -> SkippedRecipe:
    return SkippedRecipe(recipe_id=recipe_id, raw_type=raw_type, reason=reason)
