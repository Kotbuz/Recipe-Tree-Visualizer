from enum import StrEnum

from app.parser.recipe_types import (
    BLASTING,
    CAMPFIRE_COOKING,
    CRAFTING_SHAPED,
    CRAFTING_SHAPELESS,
    SMELTING,
    SMOKING,
    STONECUTTING,
    is_supported_recipe_type,
    normalize_recipe_type,
)

__all__ = [
    "RecipeType",
    "CANONICAL_TO_RECIPE_TYPE",
    "is_supported_recipe_type",
    "normalize_recipe_type",
]


class RecipeType(StrEnum):
    CRAFTING_SHAPED = CRAFTING_SHAPED
    CRAFTING_SHAPELESS = CRAFTING_SHAPELESS
    SMELTING = SMELTING
    BLASTING = BLASTING
    SMOKING = SMOKING
    CAMPFIRE_COOKING = CAMPFIRE_COOKING
    STONECUTTING = STONECUTTING


CANONICAL_TO_RECIPE_TYPE: dict[str, RecipeType] = {
    CRAFTING_SHAPED: RecipeType.CRAFTING_SHAPED,
    CRAFTING_SHAPELESS: RecipeType.CRAFTING_SHAPELESS,
    SMELTING: RecipeType.SMELTING,
    BLASTING: RecipeType.BLASTING,
    SMOKING: RecipeType.SMOKING,
    CAMPFIRE_COOKING: RecipeType.CAMPFIRE_COOKING,
    STONECUTTING: RecipeType.STONECUTTING,
}
