from app.services.item_matching import items_match
from app.services.recipe_service import _resolve_vanilla_jar_path, recipe_service
import pytest


def _require_recipe_source(version: str = "26.2") -> None:
    if recipe_service.get_recipes(version):
        return
    pytest.skip(f"No recipe source found for Minecraft version {version}")


def test_search_recipes_requires_filter() -> None:
    _require_recipe_source()
    assert recipe_service.search_recipes(version="26.2") == []


def test_search_recipes_by_output_substring() -> None:
    _require_recipe_source()
    results = recipe_service.search_recipes(version="26.2", query="oak planks", limit=10)
    assert results
    assert any("oak planks" in output.name.lower() for recipe in results for output in recipe.outputs)


def test_search_recipes_by_produces_item() -> None:
    _require_recipe_source()
    results = recipe_service.search_recipes(version="26.2", produces_item="oak planks", limit=10)
    assert results
    assert any(
        items_match("oak planks", output.name)
        for recipe in results
        for output in recipe.outputs
    )
