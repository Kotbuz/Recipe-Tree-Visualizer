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


# Поздний импорт разрывает циклическую зависимость с extensions.
from app.recipes.extensions import default_category_extensions  # noqa: E402


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
        "ae2:smelt": "Печь",
        "ae2:grind": "Камень пробуждения",
        "ae2:press": "Высекатель",
        "ae2:inscribe": "Высекатель",
        "ae2:macerator": "Дробитель IC2",
        "ae2:pulverizer": "Дробитель TE",
        "ae2:mekcrusher": "Дробитель Mekanism",
        "ae2:mekechamber": "Химкамера Mekanism",
        "ae2:hccrusher": "Дробитель Hydraulicraft",
        "ae2:crusher": "Дробитель RotaryCraft",
        "custommachinery:custom_machine": "Custom Machinery",
    }
    if raw_type in mapping:
        return mapping[raw_type]
    raw = raw_type.split(":", 1)[1] if ":" in raw_type else raw_type
    return raw.replace("_", " ").capitalize()
