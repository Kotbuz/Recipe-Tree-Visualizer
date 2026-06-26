from __future__ import annotations

from typing import Any

from app.recipes.loaders.ore_dict_loader import OreDictEntry

_AIR_INGREDIENT = {"item": "minecraft:air"}

# Fallback repairs for broken forge:ore_shaped exports where ore lists were serialized as air.
_RESULT_SYMBOL_ORE: dict[str, dict[str, str]] = {
    "minecraft:stick": {"A": "plankWood"},
    "minecraft:torch": {"A": "stickWood", "B": "dustCoal"},
    "minecraft:chest": {"A": "plankWood"},
    "minecraft:furnace": {"A": "cobblestone"},
    "minecraft:wooden_sword": {"A": "plankWood", "B": "stickWood"},
    "minecraft:wooden_pickaxe": {"A": "plankWood", "B": "stickWood"},
    "minecraft:wooden_axe": {"A": "plankWood", "B": "stickWood"},
    "minecraft:wooden_shovel": {"A": "plankWood", "B": "stickWood"},
    "minecraft:wooden_hoe": {"A": "plankWood", "B": "stickWood"},
    "minecraft:ladder": {"A": "stickWood"},
    "minecraft:fence": {"A": "stickWood", "B": "plankWood"},
    "minecraft:crafting_table": {"A": "plankWood"},
}


def repair_exported_forge_recipe(
    data: dict[str, object],
    *,
    ore_dict: dict[str, OreDictEntry],
) -> dict[str, object]:
    raw_type = data.get("type")
    if not isinstance(raw_type, str) or "ore_" not in raw_type:
        return data

    key = data.get("key")
    if not isinstance(key, dict):
        return data

    result = data.get("result")
    result_item = _result_item_id(result)
    symbol_ores = _RESULT_SYMBOL_ORE.get(result_item, {})
    if not symbol_ores:
        return data

    repaired_key: dict[str, Any] = dict(key)
    changed = False
    for symbol, ingredient in key.items():
        if ingredient != _AIR_INGREDIENT and ingredient != {"item": "minecraft:air"}:
            continue
        ore_name = symbol_ores.get(symbol)
        if ore_name is None or ore_name not in ore_dict:
            continue
        repaired_key[symbol] = {"type": "forge:ore_dict", "ore": ore_name}
        changed = True

    if not changed:
        return data

    repaired = dict(data)
    repaired["key"] = repaired_key
    return repaired


def _result_item_id(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        item = result.get("item") or result.get("id")
        if isinstance(item, str):
            return item
    return ""
