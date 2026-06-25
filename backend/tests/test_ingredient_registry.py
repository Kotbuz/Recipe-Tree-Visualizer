import json
import zipfile
from pathlib import Path

from app.recipes.loaders.tag_loader import TagLoader, normalize_tag_id
from app.recipes.registry import IngredientRegistry
import pytest


def test_normalize_tag_id() -> None:
    assert normalize_tag_id("minecraft:planks") == "tag:minecraft:planks"
    assert normalize_tag_id("tag:minecraft:planks") == "tag:minecraft:planks"
    assert normalize_tag_id("#minecraft:planks") == "tag:minecraft:planks"


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
    assert not registry.ingredient_matches("diamond", "tag:minecraft:planks")


def test_ingredient_registry_resolve_alias() -> None:
    registry = IngredientRegistry()
    assert registry.resolve_alias("planks") == "oak planks"
    assert registry.resolve_alias("stick") == "stick"


def test_get_version_registry_without_jar() -> None:
    from app.recipes.registry import get_version_ingredient_registry

    registry = get_version_ingredient_registry("missing-version-xyz-123")
    assert registry.resolve_tag("tag:minecraft:planks") == []
