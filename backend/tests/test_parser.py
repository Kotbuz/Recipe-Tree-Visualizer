from pathlib import Path

import pytest
from app.indexer.mod_registry import registry
from app.parser.jar_parser import JarParser
from app.parser.loaders import ModLoader
from app.parser.recipe_types import normalize_recipe_type
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


def test_natures_compass_builds_mod_index() -> None:
    index = JarParser().parse_mod(str(NATURES_COMPASS_JAR))

    assert index.loader == ModLoader.NEOFORGE
    assert len(index.recipes) == 2
    assert index.skipped_recipe_count == 0

    shaped = index.recipes["naturescompass:natures_compass"]
    assert {part.item_id: part.amount for part in shaped.inputs} == {
        "tag:saplings": 4.0,
        "tag:logs": 4.0,
        "minecraft:compass": 1.0,
    }


def test_natures_compass_registers_in_registry() -> None:
    summary = mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)])[0]

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
    index = JarParser().parse_mod(str(STORAGE_DRAWERS_JAR))

    assert index.loader == ModLoader.FABRIC
    assert len(index.recipes) == 127
    assert index.skipped_recipe_count == 5

    recipe = index.recipes["storagedrawers:acacia_full_drawers_1"]
    assert recipe.machine_id == "minecraft:crafting_table"
    assert {part.item_id: part.amount for part in recipe.inputs} == {
        "minecraft:acacia_planks": 6.0,
        "tag:c:chests/wooden": 1.0,
    }
    assert recipe.outputs[0].item_id == "storagedrawers:acacia_full_drawers_1"


def test_storage_drawers_search_and_recipes() -> None:
    mod_service.upload_mods_from_paths([str(STORAGE_DRAWERS_JAR)])

    items = registry.search_items("acacia_full")
    assert any(item.id == "storagedrawers:acacia_full_drawers_1" for item in items)

    recipes = registry.get_recipes_for_item("storagedrawers:acacia_full_drawers_1")
    assert len(recipes) == 1
