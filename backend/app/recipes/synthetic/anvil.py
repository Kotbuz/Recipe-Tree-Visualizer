from __future__ import annotations

from pathlib import Path

from app.parser.recipe_types import ANVIL_REPAIR
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType

_TOOL_TAGS = (
    "tag:minecraft:pickaxes",
    "tag:minecraft:axes",
    "tag:minecraft:shovels",
    "tag:minecraft:hoes",
    "tag:minecraft:swords",
)

_ARMOR_TAGS = (
    "tag:minecraft:head_armor",
    "tag:minecraft:chest_armor",
    "tag:minecraft:leg_armor",
    "tag:minecraft:foot_armor",
)

_TOOL_MATERIALS: dict[str, str] = {
    "wooden": "tag:minecraft:planks",
    "stone": "minecraft:cobblestone",
    "iron": "minecraft:iron_ingot",
    "golden": "minecraft:gold_ingot",
    "diamond": "minecraft:diamond",
    "netherite": "minecraft:netherite_ingot",
    "copper": "minecraft:copper_ingot",
}

_ARMOR_MATERIALS: dict[str, str] = {
    "leather": "minecraft:leather",
    "chainmail": "minecraft:iron_ingot",
    "copper": "minecraft:copper_ingot",
    "iron": "minecraft:iron_ingot",
    "golden": "minecraft:gold_ingot",
    "diamond": "minecraft:diamond",
    "netherite": "minecraft:netherite_ingot",
}


def build_anvil_repair_recipes(*, source: str, jar_path: Path | None) -> list[Recipe]:
    if jar_path is None or not jar_path.is_file():
        return []

    tag_map = TagLoader().load_from_jar(jar_path)
    loader = TagLoader()
    repairable_items: dict[str, str] = {}

    for tag_id in [*_TOOL_TAGS, *_ARMOR_TAGS]:
        for item_id in loader.resolve_transitive(tag_map, tag_id):
            material = _repair_material_for_item(item_id)
            if material is not None:
                repairable_items[item_id] = material

    recipes: list[Recipe] = []
    for item_id, material in sorted(repairable_items.items()):
        recipe_key = item_id.replace(":", "/")
        recipes.append(
            Recipe(
                id=f"minecraft:synthetic/anvil/repair/{recipe_key}",
                recipe_type=RecipeType.ANVIL_REPAIR,
                category_id="minecraft:anvil_repair",
                catalyst_id="minecraft:anvil",
                inputs=[
                    RecipeIO(item_id=item_id, amount=1.0),
                    RecipeIO(item_id=material, amount=1.0),
                ],
                outputs=[RecipeIO(item_id=item_id, amount=1.0)],
                duration_ticks=None,
                source=source,
                mod_id="minecraft",
                raw_type=f"minecraft:{ANVIL_REPAIR}",
            )
        )

    return recipes


def _repair_material_for_item(item_id: str) -> str | None:
    if ":" not in item_id:
        return None

    _, local_name = item_id.split(":", 1)
    for material, repair_item in _TOOL_MATERIALS.items():
        if local_name.startswith(f"{material}_"):
            return repair_item

    for material, repair_item in _ARMOR_MATERIALS.items():
        if local_name.startswith(f"{material}_"):
            return repair_item

    return None
