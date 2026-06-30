import pytest
from app.recipes.ingredients.resolver import IngredientResolver
from app.recipes.loaders.ore_dict_loader import load_ore_dict
from app.recipes.loaders.recipe_paths import (
    discover_recipe_file,
    is_recipe_entry,
    recipe_layout_for_version,
)


def test_recipe_layout_for_version() -> None:
    assert recipe_layout_for_version("1.7.10") == "jvm"
    assert recipe_layout_for_version("1.12.2") == "assets"
    assert recipe_layout_for_version("1.16.5") == "data"
    assert recipe_layout_for_version("26.2") == "data"


def test_discover_assets_recipe_path() -> None:
    path = "assets/minecraft/recipes/oak_planks.json"
    assert is_recipe_entry(path)
    discovered = discover_recipe_file(path)
    assert discovered is not None
    assert discovered.recipe_id == "minecraft:oak_planks"


def test_discover_data_recipe_path() -> None:
    path = "data/create/recipes/gearbox.json"
    assert is_recipe_entry(path)
    discovered = discover_recipe_file(path)
    assert discovered is not None
    assert discovered.recipe_id == "create:gearbox"


def test_discover_skips_advancements_and_aerecipes() -> None:
    assert not is_recipe_entry("data/minecraft/advancements/recipes/foo.json")
    assert not is_recipe_entry("assets/appliedenergistics2/aerecipes/grinder/bonemeal.json")


def test_ingredient_resolver_modern_tag_strings() -> None:
    resolver = IngredientResolver(version="26.2", ore_dict={})

    parsed = resolver.resolve("#minecraft:oak_logs")
    assert parsed.item_id == "tag:minecraft:oak_logs"

    parsed = resolver.resolve({"tag": "minecraft:planks"})
    assert parsed.item_id == "tag:minecraft:planks"


def test_ingredient_resolver_ore_dict_and_metadata() -> None:
    ore_dict = load_ore_dict("1.12.2")
    resolver = IngredientResolver(version="1.12.2", ore_dict=ore_dict)

    parsed = resolver.resolve({"ore": "gemDiamond", "type": "forge:ore_dict"})
    assert parsed.item_id == "minecraft:diamond"

    parsed = resolver.resolve({"item": "#ENDER_PEARL"})
    assert parsed.item_id == "minecraft:ender_pearl"

    parsed = resolver.resolve({"item": "minecraft:planks", "data": 0})
    assert parsed.item_id == "minecraft:planks"
    assert parsed.metadata == 0


@pytest.mark.skipif(
    not __import__("pathlib")
    .Path(__file__)
    .resolve()
    .parents[2]
    .joinpath("../MinecraftVersions/1.12.2/client.jar")
    .is_file(),
    reason="1.12.2 client.jar not available",
)
def test_vanilla_1_12_2_loads_crafting_recipes() -> None:
    from app.recipes.providers.vanilla_jar import VanillaJarProvider

    result = VanillaJarProvider().load("1.12.2")
    assert len(result.recipes) > 100
    oak_planks = next(recipe for recipe in result.recipes if recipe.id == "minecraft:oak_planks")
    assert oak_planks.inputs[0].item_id == "minecraft:log"
    assert oak_planks.inputs[0].metadata == 0
