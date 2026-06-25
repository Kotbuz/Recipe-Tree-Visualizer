from app.services.icon_registry import collect_recipe_icon_ids, icon_id_for_ingredient
from app.services.recipe_service import _resolve_vanilla_jar_path
import pytest


def _require_vanilla_jar(version: str = "26.2") -> None:
    if _resolve_vanilla_jar_path(version) is None:
        pytest.skip(f"No vanilla jar found for version {version}")


def test_icon_id_for_item_uses_registry() -> None:
    _require_vanilla_jar()
    assert icon_id_for_ingredient("minecraft:oak_planks", "26.2") == "oak_planks"


def test_icon_id_for_tag_uses_alias() -> None:
    _require_vanilla_jar()
    assert icon_id_for_ingredient("tag:minecraft:planks", "26.2") == "oak_planks"


def test_icon_id_for_acacia_logs_tag_uses_member() -> None:
    _require_vanilla_jar()
    assert icon_id_for_ingredient("tag:minecraft:acacia_logs", "26.2") == "acacia_log"


def test_collect_recipe_icon_ids_includes_recipe_items() -> None:
    _require_vanilla_jar()
    icon_ids = collect_recipe_icon_ids("26.2")

    assert "stick" in icon_ids
    assert "oak_planks" in icon_ids
