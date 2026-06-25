from __future__ import annotations

from typing import TYPE_CHECKING

from app.recipes.category import display_name_for_raw_type
from app.recipes.models import Recipe
from app.schemas.recipe_file import RecipeItem, RecipeSummary

if TYPE_CHECKING:
    from app.recipes.registry import IngredientRegistry


def item_id_to_display_name(item_id: str) -> str:
    raw = item_id.removeprefix("tag:")
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return raw.replace("_", " ")


def _icon_id_for_part(
    item_id: str,
    *,
    ingredient_registry: IngredientRegistry | None = None,
    version: str | None = None,
) -> str:
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
                name=item_id_to_display_name(part.item_id),
                amount=int(part.amount),
                item_id=part.item_id,
                icon_id=_icon_id_for_part(
                    part.item_id,
                    ingredient_registry=ingredient_registry,
                    version=version,
                ),
            )
            for part in recipe.inputs
        ],
        outputs=[
            RecipeItem(
                name=item_id_to_display_name(part.item_id),
                amount=int(part.amount),
                item_id=part.item_id,
                icon_id=_icon_id_for_part(
                    part.item_id,
                    ingredient_registry=ingredient_registry,
                    version=version,
                ),
            )
            for part in recipe.outputs
        ],
    )
