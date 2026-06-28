from __future__ import annotations

import json
from pathlib import Path

from app.recipes.loaders.tag_snapshot_loader import (
    common_tag_aliases,
    common_tag_display_name,
    load_tag_snapshot,
)
from app.recipes.registry import IngredientRegistry


def test_common_tag_display_name() -> None:
    assert common_tag_display_name("tag:c:dusts/redstone") == "Redstone Dust"
    assert common_tag_display_name("tag:c:gems/diamond") == "Diamond"
    assert common_tag_display_name("tag:c:glass_blocks/cheap") == "Cheap Glass Block"
    assert common_tag_display_name("tag:c:gears/stone") == "Stone Gear"
    assert common_tag_display_name("tag:c:ingots/copper") == "Copper Ingot"
    assert common_tag_display_name("tag:c:dusts/alltheores_quartz") == "Quartz Dust"


def test_common_tag_aliases() -> None:
    aliases = common_tag_aliases("tag:c:dusts/redstone")
    assert aliases["dusts/redstone"] == "Redstone Dust"
    assert aliases["dusts redstone"] == "Redstone Dust"
    assert aliases["redstone dust"] == "Redstone Dust"


def test_load_bundled_tag_snapshot() -> None:
    snapshot = load_tag_snapshot("1.21.1")
    assert "tag:c:dusts/redstone" in snapshot
    assert "minecraft:redstone" in snapshot["tag:c:dusts/redstone"]
    assert "tag:c:glass_blocks/cheap" in snapshot
    assert "minecraft:glass" in snapshot["tag:c:glass_blocks/cheap"]
    assert "tag:c:gears/stone" in snapshot


def test_registry_resolves_common_tags_from_snapshot() -> None:
    registry = IngredientRegistry()
    registry.load_version("1.21.1")
    registry.register("tag:c:dusts/redstone")

    assert registry.ingredient_matches("redstone dust", "tag:c:dusts/redstone")
    assert registry.ingredient_matches("minecraft:redstone", "tag:c:dusts/redstone")
    assert registry.ingredient_matches("tag:c:dusts/redstone", "minecraft:redstone")
    assert registry.ingredient_matches("cheap glass block", "tag:c:glass_blocks/cheap")


def test_tag_icons_use_representative_members() -> None:
    registry = IngredientRegistry()
    registry.load_version("1.21.1")

    stone_gear = registry.register("tag:c:gears/stone")
    assert stone_gear.icon_id == "alltheores_stone_gear"

    leathers = registry.register("tag:c:leathers")
    assert leathers.icon_id == "leather"


def test_bundled_snapshot_file_is_valid_json() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "tag_snapshots" / "1.21.1.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert len(payload) >= 200
