import json
import zipfile
from pathlib import Path

import pytest
from app.recipes.loaders.tag_loader import TagLoader, normalize_tag_id
from app.recipes.registry import IngredientRegistry


def test_normalize_tag_id() -> None:
    assert normalize_tag_id("minecraft:planks") == "tag:minecraft:planks"
    assert normalize_tag_id("tag:minecraft:planks") == "tag:minecraft:planks"
    assert normalize_tag_id("#minecraft:planks") == "tag:minecraft:planks"


def test_tag_loader_parses_nested_tag_paths(tmp_path: Path) -> None:
    jar_path = tmp_path / "nested-tags.jar"
    tag_json = json.dumps({"values": ["minecraft:redstone"]}).encode("utf-8")
    cheap_glass_json = json.dumps({"values": ["minecraft:glass"]}).encode("utf-8")

    with zipfile.ZipFile(jar_path, "w") as archive:
        archive.writestr("data/c/tags/item/dusts/redstone.json", tag_json)
        archive.writestr("data/c/tags/item/glass_blocks/cheap.json", cheap_glass_json)

    loader = TagLoader()
    tags = loader.load_from_jar(jar_path)

    assert "tag:c:dusts/redstone" in tags
    assert "minecraft:redstone" in tags["tag:c:dusts/redstone"]
    assert "tag:c:glass_blocks/cheap" in tags
    assert "minecraft:glass" in tags["tag:c:glass_blocks/cheap"]


def test_tag_loader_parses_values(tmp_path: Path) -> None:
    jar_path = tmp_path / "tags.jar"
    tag_json = json.dumps(
        {
            "values": [
                "minecraft:oak_planks",
                "minecraft:spruce_planks",
                "#minecraft:logs",
            ]
        }
    ).encode("utf-8")
    logs_json = json.dumps({"values": ["minecraft:oak_log"]}).encode("utf-8")

    with zipfile.ZipFile(jar_path, "w") as archive:
        archive.writestr("data/minecraft/tags/item/planks.json", tag_json)
        archive.writestr("data/minecraft/tags/item/logs.json", logs_json)

    loader = TagLoader()
    tags = loader.load_from_jar(jar_path)

    assert "tag:minecraft:planks" in tags
    assert "minecraft:oak_planks" in tags["tag:minecraft:planks"]
    assert loader.resolve_transitive(tags, "tag:minecraft:planks")
    assert "minecraft:oak_planks" in loader.resolve_transitive(tags, "tag:minecraft:planks")
    assert "minecraft:oak_log" in loader.resolve_transitive(tags, "tag:minecraft:planks")


def test_ingredient_registry_matches_tag_members() -> None:
    registry = IngredientRegistry()
    registry._tag_members = {
        "tag:minecraft:planks": frozenset(
            {"minecraft:oak_planks", "minecraft:spruce_planks"},
        ),
    }
    registry.register("tag:minecraft:planks")

    assert registry.ingredient_matches("oak planks", "tag:minecraft:planks")
    assert registry.ingredient_matches("spruce planks", "tag:minecraft:planks")
    assert registry.ingredient_matches("tag:minecraft:planks", "minecraft:oak_planks")
    assert registry.ingredient_matches("tag:minecraft:planks", "minecraft:spruce_planks")
    assert registry.ingredient_matches("planks", "minecraft:birch_planks")
    assert not registry.ingredient_matches("diamond", "tag:minecraft:planks")


def test_ingredient_registry_matches_stone_tags() -> None:
    from app.recipes.registry import get_version_ingredient_registry
    from app.services.recipe_service import _resolve_vanilla_jar_path

    if _resolve_vanilla_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present")

    registry = get_version_ingredient_registry("26.2")
    assert registry.ingredient_matches(
        "tag:minecraft:stone_crafting_materials", "minecraft:cobblestone"
    )
    assert registry.ingredient_matches(
        "minecraft:cobblestone", "tag:minecraft:stone_crafting_materials"
    )
    assert registry.ingredient_matches("tag:minecraft:stone_crafting_materials", "cobblestone")
    assert registry.ingredient_matches("stone tool materials", "minecraft:cobblestone")


def test_ingredient_registry_resolve_alias() -> None:
    registry = IngredientRegistry()
    assert registry.resolve_alias("planks") == "oak planks"
    assert registry.resolve_alias("stick") == "stick"


def test_get_version_registry_without_jar() -> None:
    from app.recipes.registry import get_version_ingredient_registry

    registry = get_version_ingredient_registry("missing-version-xyz-123")
    assert registry.resolve_tag("tag:minecraft:planks") == []
