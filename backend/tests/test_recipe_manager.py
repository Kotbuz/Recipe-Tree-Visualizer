from app.recipes.adapters import item_id_to_display_name
from app.recipes.focus import RecipeIngredientRole
from app.recipes.manager import recipe_manager
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.types import RecipeType
from app.services.recipe_service import _resolve_vanilla_jar_path, recipe_service
import pytest


def test_json_recipe_parser_shapeless_stick() -> None:
    parser = JsonRecipeParser()
    data = {
        "type": "minecraft:crafting_shaped",
        "pattern": ["A", "A"],
        "key": {"A": {"item": "minecraft:oak_planks"}},
        "result": {"item": "minecraft:stick", "count": 4},
    }

    recipe = parser.parse(
        "minecraft:stick",
        data,
        source="vanilla:26.2",
        mod_id="minecraft",
    )

    assert recipe is not None
    assert recipe.id == "minecraft:stick"
    assert recipe.recipe_type == RecipeType.CRAFTING_SHAPED
    assert recipe.catalyst_id == "minecraft:crafting_table"
    assert recipe.outputs[0].item_id == "minecraft:stick"
    assert recipe.outputs[0].amount == 4.0
    assert len(recipe.inputs) == 1
    assert recipe.inputs[0].item_id == "minecraft:oak_planks"
    assert recipe.inputs[0].amount == 2.0


def test_json_recipe_parser_tag_ingredient() -> None:
    parser = JsonRecipeParser()
    data = {
        "type": "minecraft:crafting_shapeless",
        "ingredients": [{"tag": "minecraft:planks"}],
        "result": "minecraft:chest",
    }

    recipe = parser.parse(
        "minecraft:chest",
        data,
        source="vanilla:26.2",
        mod_id="minecraft",
    )

    assert recipe is not None
    assert recipe.inputs[0].item_id == "tag:minecraft:planks"


def test_item_id_to_display_name() -> None:
    assert item_id_to_display_name("minecraft:oak_planks") == "oak planks"
    assert item_id_to_display_name("tag:minecraft:planks") == "planks"


def _require_recipe_source(version: str = "26.2") -> None:
    recipes = recipe_manager.get_version_recipes(version)
    if recipes:
        return
    if _resolve_vanilla_jar_path(version) is not None:
        return
    pytest.skip(f"No recipe source found for Minecraft version {version}")


def test_recipe_manager_loads_recipes_with_item_ids() -> None:
    _require_recipe_source()
    recipes = recipe_manager.get_version_recipes("26.2")
    assert recipes
    assert all(":" in recipe.id for recipe in recipes)
    assert all(part.item_id for recipe in recipes for part in recipe.inputs + recipe.outputs)


def test_recipe_manager_focus_output() -> None:
    _require_recipe_source()
    results = (
        recipe_manager.lookup("26.2")
        .focus("oak planks", RecipeIngredientRole.OUTPUT)
        .limit(5)
        .all()
    )
    assert results
    assert all(
        any(part.item_id.endswith("oak_planks") for part in recipe.outputs) for recipe in results
    )


def test_recipe_service_still_returns_summaries() -> None:
    _require_recipe_source()
    results = recipe_service.search_recipes(version="26.2", query="oak planks", limit=10)
    assert results
    assert any("oak planks" in output.name.lower() for recipe in results for output in recipe.outputs)


def test_vanilla_provider_skips_unsupported_recipes() -> None:
    provider = VanillaJarProvider()
    result = provider.load("missing-version-xyz")
    assert result.recipes == []
    assert result.skipped == []
