from __future__ import annotations

from typing import TYPE_CHECKING

from app.recipes.category import display_name_for_raw_type
from app.recipes.legacy_item_icons import (
    resolve_legacy_display_name,
    resolve_legacy_icon_id,
)
from app.recipes.loaders.item_catalog_loader import (
    resolve_catalog_display_name,
    resolve_catalog_icon_id,
)
from app.recipes.models import Recipe
from app.schemas.recipe_file import RecipeItem, RecipeSummary

if TYPE_CHECKING:
    from app.recipes.registry import IngredientRegistry


from app.recipes.loaders.tag_snapshot_loader import common_tag_display_name


def item_id_to_display_name(item_id: str) -> str:
    tagged = common_tag_display_name(item_id)
    if tagged is not None:
        return tagged
    raw = item_id.removeprefix("tag:")
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return raw.replace("_", " ")


def _display_name_for_part(
    item_id: str,
    *,
    metadata: int | None = None,
    version: str | None = None,
) -> str:
    if version is not None:
        catalog_name = resolve_catalog_display_name(item_id, metadata, version=version)
        if catalog_name is not None:
            return catalog_name
        legacy_name = resolve_legacy_display_name(item_id, metadata, version=version)
        if legacy_name is not None:
            return legacy_name
    return item_id_to_display_name(item_id)


def _icon_id_for_part(
    item_id: str,
    *,
    metadata: int | None = None,
    ingredient_registry: IngredientRegistry | None = None,
    version: str | None = None,
) -> str:
    if version is not None:
        catalog_icon = resolve_catalog_icon_id(item_id, metadata, version=version)
        if catalog_icon is not None:
            return catalog_icon
        legacy_icon = resolve_legacy_icon_id(item_id, metadata, version=version)
        if legacy_icon is not None:
            return legacy_icon

    if ingredient_registry is not None:
        return ingredient_registry.register(item_id).icon_id

    if version is not None:
        from app.services.icon_registry import icon_id_for_ingredient

        return icon_id_for_ingredient(item_id, version)

    raw = item_id.split(":", maxsplit=1)[-1]
    return raw.replace(" ", "_").lower()


def to_recipe_summary(
    recipe: Recipe,
    *,
    ingredient_registry: IngredientRegistry | None = None,
    version: str | None = None,
) -> RecipeSummary:
    machine_type = recipe.raw_type or recipe.recipe_type.value
    return RecipeSummary(
        recipe_id=recipe.id,
        machine_type=machine_type,
        machine_name=display_name_for_raw_type(machine_type),
        inputs=[
            RecipeItem(
                name=_display_name_for_part(
                    part.item_id, metadata=part.metadata, version=version
                ),
                amount=int(part.amount),
                item_id=part.item_id,
                metadata=part.metadata,
                icon_id=_icon_id_for_part(
                    part.item_id,
                    metadata=part.metadata,
                    ingredient_registry=ingredient_registry,
                    version=version,
                ),
            )
            for part in recipe.inputs
        ],
        outputs=[
            RecipeItem(
                name=_display_name_for_part(
                    part.item_id, metadata=part.metadata, version=version
                ),
                amount=int(part.amount),
                item_id=part.item_id,
                metadata=part.metadata,
                icon_id=_icon_id_for_part(
                    part.item_id,
                    metadata=part.metadata,
                    ingredient_registry=ingredient_registry,
                    version=version,
                ),
            )
            for part in recipe.outputs
        ],
        duration_ticks=recipe.duration_ticks,
    )
