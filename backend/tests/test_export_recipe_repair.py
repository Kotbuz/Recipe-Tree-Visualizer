from app.recipes.loaders.export_recipe_repair import repair_exported_forge_recipe
from app.recipes.loaders.ore_dict_loader import OreDictEntry


def test_repair_exported_forge_recipe_fixes_stick_planks() -> None:
    data = {
        "type": "forge:ore_shaped",
        "pattern": ["A", "A"],
        "key": {"A": {"item": "minecraft:air"}},
        "result": {"item": "minecraft:stick", "count": 4},
    }
    ore_dict = {"plankWood": OreDictEntry(item_id="minecraft:planks", metadata=None)}

    repaired = repair_exported_forge_recipe(data, ore_dict=ore_dict)

    assert repaired["key"]["A"] == {"type": "forge:ore_dict", "ore": "plankWood"}


def test_repair_exported_forge_recipe_leaves_unknown_results() -> None:
    data = {
        "type": "forge:ore_shaped",
        "pattern": ["A"],
        "key": {"A": {"item": "minecraft:air"}},
        "result": {"item": "minecraft:unknown_item"},
    }

    repaired = repair_exported_forge_recipe(data, ore_dict={})

    assert repaired["key"]["A"] == {"item": "minecraft:air"}
