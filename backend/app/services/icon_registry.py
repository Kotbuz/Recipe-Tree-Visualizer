from __future__ import annotations

from app.recipes.manager import recipe_manager
from app.recipes.registry import get_version_ingredient_registry


def icon_id_for_ingredient(ingredient_id: str, version: str) -> str:
    registry = get_version_ingredient_registry(version)
    ingredient = registry.register(ingredient_id)
    return ingredient.icon_id


def collect_recipe_icon_ids(
    version: str,
    *,
    profile_id: str | None = None,
    include_mods: bool = True,
) -> list[str]:
    from app.recipes.registry import get_profile_ingredient_registry

    get_profile_ingredient_registry(version, profile_id)
    icon_ids: set[str] = set()

    recipes = recipe_manager.get_version_recipes(
        version,
        profile_id=profile_id,
        include_mods=include_mods,
        include_synthetic=True,
    )
    for recipe in recipes:
        for part in [*recipe.inputs, *recipe.outputs]:
            icon_ids.add(icon_id_for_ingredient(part.item_id, version))

    return sorted(icon_ids)
