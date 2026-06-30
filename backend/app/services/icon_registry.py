from __future__ import annotations

import zipfile
from pathlib import Path

from app.recipes.manager import recipe_manager
from app.recipes.registry import IngredientRegistry
from app.services.jar_paths import collect_profile_jar_paths

_MODEL_MARKERS = ("/models/item/", "/models/block/")
_ITEMS_MARKER = "/items/"


def icon_id_for_ingredient(
    ingredient_id: str,
    version: str,
    *,
    profile_id: str | None = None,
) -> str:
    from app.recipes.registry import get_profile_ingredient_registry

    registry = get_profile_ingredient_registry(version, profile_id)
    ingredient = registry.register(ingredient_id, version=version)
    return ingredient.icon_id


def collect_recipe_icon_ids(
    version: str,
    *,
    profile_id: str | None = None,
    include_mods: bool = True,
) -> list[str]:
    from app.recipes.registry import get_profile_ingredient_registry

    registry = get_profile_ingredient_registry(version, profile_id)
    icon_ids: set[str] = set()

    recipes = recipe_manager.get_version_recipes(
        version,
        profile_id=profile_id,
        include_mods=include_mods,
        include_synthetic=True,
    )
    for recipe in recipes:
        for part in [*recipe.inputs, *recipe.outputs]:
            ingredient = registry.register(part.item_id, metadata=part.metadata, version=version)
            icon_ids.add(ingredient.icon_id)

    return sorted(icon_ids)


def model_entry_to_icon_id(entry: str) -> str | None:
    """assets/minecraft/models/item/stick.json → stick; create/models/item/x → create_x."""
    normalized = entry.replace("\\", "/")
    if not normalized.endswith(".json"):
        return None

    if _ITEMS_MARKER in normalized and "/models/" not in normalized:
        namespace = normalized.split("assets/", 1)[-1].split("/", 1)[0]
        leaf = normalized.rsplit("/", 1)[-1].removesuffix(".json")
        if not leaf:
            return None
        item_id = f"{namespace}:{leaf}" if namespace else leaf
        return IngredientRegistry._item_id_to_icon_id(item_id)

    for marker in _MODEL_MARKERS:
        if marker not in normalized:
            continue
        namespace = normalized.split("assets/", 1)[-1].split("/", 1)[0]
        rest = normalized.split(marker, 1)[-1].removesuffix(".json")
        if not rest:
            return None
        flat = rest.replace("/", "_").lower()
        if namespace == "minecraft":
            return flat
        return f"{namespace}_{flat}"
    return None


def collect_jar_icon_ids(
    version: str,
    *,
    profile_id: str | None = None,
) -> list[str]:
    """Полный скан jar: item/block-модели и items/*.json (H2c)."""
    icon_ids: set[str] = set()
    for jar_path in collect_profile_jar_paths(version, profile_id=profile_id):
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.namelist():
                    icon_id = model_entry_to_icon_id(entry)
                    if icon_id:
                        icon_ids.add(icon_id)
        except (OSError, zipfile.BadZipFile):
            continue
    return sorted(icon_ids)


def collect_required_icon_ids(
    version: str,
    *,
    profile_id: str | None = None,
    include_mods: bool = True,
) -> list[str]:
    """Иконки для рендера: полный скан jar + предметы из рецептов (на всякий случай)."""
    icon_ids = set(collect_jar_icon_ids(version, profile_id=profile_id))
    icon_ids.update(
        collect_recipe_icon_ids(version, profile_id=profile_id, include_mods=include_mods)
    )
    return sorted(icon_ids)
