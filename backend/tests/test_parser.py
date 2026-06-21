from pathlib import Path

from app.indexer.mod_registry import registry
from app.parser.jar_parser import JarParser
from app.services.mod_service import mod_service

FIXTURE_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"


def test_natures_compass_extracts_two_recipes() -> None:
    parser = JarParser()
    raw = parser.extract(str(FIXTURE_JAR))

    assert raw.meta.mod_id == "naturescompass"
    assert raw.meta.name == "Nature's Compass"
    assert len(raw.recipe_files) == 2
    recipe_ids = {recipe.recipe_id for recipe in raw.recipe_files}
    assert recipe_ids == {
        "naturescompass:natures_compass",
        "naturescompass:repair_natures_compass",
    }


def test_natures_compass_builds_mod_index() -> None:
    index = JarParser().parse_mod(str(FIXTURE_JAR))

    assert index.mod_id == "naturescompass"
    assert len(index.recipes) == 2
    assert len(index.machines) == 1
    assert "minecraft:crafting_table" in index.machines

    shaped = index.recipes["naturescompass:natures_compass"]
    assert shaped.machine_id == "minecraft:crafting_table"
    assert {part.item_id: part.amount for part in shaped.inputs} == {
        "tag:saplings": 4.0,
        "tag:logs": 4.0,
        "minecraft:compass": 1.0,
    }
    assert shaped.outputs[0].item_id == "naturescompass:naturescompass"

    repair = index.recipes["naturescompass:repair_natures_compass"]
    assert {part.item_id for part in repair.inputs} == {
        "naturescompass:naturescompass",
        "minecraft:compass",
    }


def test_natures_compass_registers_in_registry() -> None:
    summary = mod_service.upload_mods_from_paths([str(FIXTURE_JAR)])[0]

    assert summary.mod_id == "naturescompass"
    assert summary.recipe_count == 2
    assert summary.item_count >= 4

    items = registry.search_items("compass")
    item_ids = {item.id for item in items}
    assert "naturescompass:naturescompass" in item_ids
    assert "minecraft:compass" in item_ids

    recipes = registry.get_recipes_for_item("naturescompass:naturescompass")
    assert len(recipes) == 2
