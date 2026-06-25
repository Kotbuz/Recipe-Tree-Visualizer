from dataclasses import dataclass

from app.parser.recipe_types import MACHINE_BY_TYPE
from app.recipes.types import CANONICAL_TO_RECIPE_TYPE, RecipeType

_CATALYST_DISPLAY_NAMES: dict[str, str] = {
    "minecraft:crafting_table": "Верстак",
    "minecraft:furnace": "Печь",
    "minecraft:blast_furnace": "Печь",
    "minecraft:smoker": "Печь",
    "minecraft:campfire": "Печь",
    "minecraft:stonecutter": "Наковальня",
    "minecraft:brewing_stand": "Зельеварка",
    "minecraft:composter": "Компостер",
    "minecraft:anvil": "Наковальня",
}


@dataclass(frozen=True)
class RecipeCategory:
    id: str
    recipe_type: RecipeType
    catalyst_id: str
    display_name: str


def category_for_canonical_type(canonical_type: str) -> RecipeCategory:
    recipe_type = CANONICAL_TO_RECIPE_TYPE[canonical_type]
    catalyst_id = MACHINE_BY_TYPE[canonical_type]
    return RecipeCategory(
        id=f"minecraft:{canonical_type}",
        recipe_type=recipe_type,
        catalyst_id=catalyst_id,
        display_name=_CATALYST_DISPLAY_NAMES.get(catalyst_id, catalyst_id.split(":")[-1].title()),
    )


from app.recipes.extensions import default_category_extensions


def display_name_for_raw_type(raw_type: str) -> str:
    extension_name = default_category_extensions().display_name(raw_type)
    if extension_name:
        return extension_name

    mapping = {
        "minecraft:crafting_shaped": "Верстак",
        "minecraft:crafting_shapeless": "Верстак",
        "minecraft:smelting": "Печь",
        "minecraft:smoking": "Печь",
        "minecraft:blasting": "Печь",
        "minecraft:campfire_cooking": "Печь",
        "minecraft:smithing": "Наковальня",
        "minecraft:smithing_transform": "Наковальня",
        "minecraft:stonecutting": "Наковальня",
        "minecraft:brewing": "Зельеварка",
        "minecraft:composting": "Компостер",
        "minecraft:anvil_repair": "Наковальня",
    }
    if raw_type in mapping:
        return mapping[raw_type]
    if ":" in raw_type:
        raw = raw_type.split(":", 1)[1]
    else:
        raw = raw_type
    return raw.replace("_", " ").capitalize()
