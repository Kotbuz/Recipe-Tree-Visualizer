from pathlib import Path

from app.recipes.extensions import default_category_extensions
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.mod_jar import ModJarProvider

STORAGE_DRAWERS_JAR = (
    Path(__file__).parent / "fixtures" / "StorageDrawers-fabric-1.21.11-20.0.0.jar"
)


def test_forge_ore_shaped_parses_like_crafting_shaped() -> None:
    parser = JsonRecipeParser()
    data = {
        "type": "forge:ore_shaped",
        "pattern": ["I"],
        "key": {"I": {"item": "minecraft:iron_ingot"}},
        "result": "minecraft:stick",
    }

    recipe = parser.parse("testmod:test_stick", data, source="mod:testmod", mod_id="testmod")

    assert recipe is not None
    assert recipe.recipe_type.value == "crafting_shaped"
    assert recipe.raw_type == "forge:ore_shaped"
    assert recipe.inputs[0].item_id == "minecraft:iron_ingot"
    assert recipe.outputs[0].item_id == "minecraft:stick"


def test_storage_drawers_extension_recognizes_synthetic_recipes() -> None:
    parser = JsonRecipeParser()
    data = {"type": "storagedrawers:add_upgrade"}

    assert parser.can_parse(data)
    assert parser.parse("storagedrawers:add_upgrade", data, source="mod:storagedrawers") is None
    assert parser.skip_reason(data) == "synthetic in-game recipe"


def test_storage_drawers_skip_reasons_in_provider() -> None:
    result = ModJarProvider().load(str(STORAGE_DRAWERS_JAR))

    assert len(result.recipes) == 127
    assert len(result.skipped) == 5
    assert all(skip.reason == "synthetic in-game recipe" for skip in result.skipped)


def test_extension_display_names() -> None:
    registry = default_category_extensions()

    assert registry.display_name("storagedrawers:add_upgrade") == "Storage Drawers upgrade"
    assert registry.display_name("forge:ore_shaped") is None
