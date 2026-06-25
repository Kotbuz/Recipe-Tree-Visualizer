from app.services.item_matching import items_match
from app.services.recipe_service import recipe_service


def test_search_recipes_requires_filter() -> None:
    assert recipe_service.search_recipes(version="26.2") == []


def test_search_recipes_by_output_substring() -> None:
    results = recipe_service.search_recipes(version="26.2", query="oak planks", limit=10)
    assert results
    assert any("oak planks" in output.name.lower() for recipe in results for output in recipe.outputs)


def test_search_recipes_by_produces_item() -> None:
    results = recipe_service.search_recipes(version="26.2", produces_item="oak planks", limit=10)
    assert results
    assert any(
        items_match("oak planks", output.name)
        for recipe in results
        for output in recipe.outputs
    )
