from pathlib import Path

import pytest
from app.parser.jar_parser import JarParser
from app.parser.loaders import ModLoader
from app.parser.recipe_types import normalize_recipe_type
from app.recipes.providers.mod_jar import ModJarProvider
from app.services.item_service import item_service
from app.services.mod_service import mod_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"
STORAGE_DRAWERS_JAR = (
    Path(__file__).parent / "fixtures" / "StorageDrawers-fabric-1.21.11-20.0.0.jar"
)


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        ("crafting_shaped", "crafting_shaped"),
        ("minecraft:crafting_shaped", "crafting_shaped"),
        ("minecraft:crafting_shapeless", "crafting_shapeless"),
        ("forge:ore_shaped", "ore_shaped"),
        ("storagedrawers:add_upgrade", "storagedrawers:add_upgrade"),
    ],
)
def test_normalize_recipe_type(raw_type: str, expected: str) -> None:
    assert normalize_recipe_type(raw_type) == expected


def test_natures_compass_neoforge_metadata() -> None:
    raw = JarParser().extract(str(NATURES_COMPASS_JAR))

    assert raw.meta.loader == ModLoader.NEOFORGE
    assert raw.meta.mod_id == "naturescompass"
    assert len(raw.recipe_files) == 2


def test_natures_compass_builds_mod_recipes() -> None:
    result = ModJarProvider().load(str(NATURES_COMPASS_JAR))

    assert len(result.recipes) == 2
    assert len(result.skipped) == 0

    shaped = next(recipe for recipe in result.recipes if recipe.id == "naturescompass:natures_compass")
    assert {part.item_id: part.amount for part in shaped.inputs} == {
        "tag:saplings": 4.0,
        "tag:logs": 4.0,
        "minecraft:compass": 1.0,
    }


def test_natures_compass_registers_in_registry(isolated_minecraft_versions) -> None:
    summary = mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)], "26.2")[0]

    assert summary.loader == "neoforge"
    assert summary.recipe_count == 2
    assert summary.skipped_recipe_count == 0


def test_storage_drawers_fabric_metadata() -> None:
    raw = JarParser().extract(str(STORAGE_DRAWERS_JAR))

    assert raw.meta.loader == ModLoader.FABRIC
    assert raw.meta.mod_id == "storagedrawers"
    assert raw.meta.name == "Storage Drawers"
    assert len(raw.recipe_files) == 132


def test_storage_drawers_indexes_vanilla_recipes_only() -> None:
    result = ModJarProvider().load(str(STORAGE_DRAWERS_JAR))

    assert len(result.recipes) == 127
    assert len(result.skipped) == 5

    recipe = next(recipe for recipe in result.recipes if recipe.id == "storagedrawers:acacia_full_drawers_1")
    assert recipe.catalyst_id == "minecraft:crafting_table"
    assert {part.item_id: part.amount for part in recipe.inputs} == {
        "minecraft:acacia_planks": 6.0,
        "tag:c:chests/wooden": 1.0,
    }
    assert recipe.outputs[0].item_id == "storagedrawers:acacia_full_drawers_1"


def test_storage_drawers_search_and_recipes(isolated_minecraft_versions) -> None:
    mod_service.upload_mods_from_paths([str(STORAGE_DRAWERS_JAR)], "1.21.11")

    items = item_service.search_items("acacia_full", version="1.21.11")
    assert any(item.id == "storagedrawers:acacia_full_drawers_1" for item in items.items)

    recipes = item_service.get_item_recipes(
        "storagedrawers:acacia_full_drawers_1",
        version="1.21.11",
    )
    assert len(recipes.recipes) == 1
