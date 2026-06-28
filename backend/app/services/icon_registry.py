from __future__ import annotations

from app.recipes.manager import recipe_manager


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
