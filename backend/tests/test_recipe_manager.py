from app.recipes.adapters import item_id_to_display_name
from app.recipes.focus import RecipeIngredientRole
from app.recipes.manager import RecipeLookup, recipe_manager
from app.recipes.models import Recipe, RecipeIO
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
    if recipe_manager.get_version_recipes(version):
        return
    pytest.skip(f"No recipe source found for Minecraft version {version}")


def test_recipe_manager_loads_recipes_with_item_ids() -> None:
    _require_recipe_source()
    recipes = recipe_manager.get_version_recipes("26.2")
    assert recipes
    assert all(":" in recipe.id for recipe in recipes)
    assert all(part.item_id for recipe in recipes for part in recipe.inputs + recipe.outputs)


def test_recipe_lookup_focus_respects_metadata() -> None:
    brick_slab = Recipe(
        id="minecraft:export/crafting/brick_slab",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="crafting",
        catalyst_id=None,
        inputs=[RecipeIO(item_id="minecraft:brick_block", amount=1.0)],
        outputs=[RecipeIO(item_id="minecraft:stone_slab", amount=6.0, metadata=4)],
        duration_ticks=None,
        source="vanilla",
        mod_id="minecraft",
        raw_type="crafting_shaped",
    )
    quartz_slab = Recipe(
        id="minecraft:export/crafting/quartz_slab",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="crafting",
        catalyst_id=None,
        inputs=[RecipeIO(item_id="minecraft:quartz_block", amount=1.0)],
        outputs=[RecipeIO(item_id="minecraft:stone_slab", amount=6.0, metadata=7)],
        duration_ticks=None,
        source="vanilla",
        mod_id="minecraft",
        raw_type="crafting_shaped",
    )

    lookup = RecipeLookup((brick_slab, quartz_slab), None, "1.7.10")

    all_slabs = lookup.focus("minecraft:stone_slab", RecipeIngredientRole.OUTPUT).all()
    assert len(all_slabs) == 2

    quartz_only = lookup.focus(
        "minecraft:stone_slab",
        RecipeIngredientRole.OUTPUT,
        metadata=7,
    ).all()
    assert len(quartz_only) == 1
    assert quartz_only[0].id == "minecraft:export/crafting/quartz_slab"

    brick_only = lookup.focus(
        "minecraft:stone_slab",
        RecipeIngredientRole.OUTPUT,
        metadata=4,
    ).all()
    assert len(brick_only) == 1
    assert brick_only[0].id == "minecraft:export/crafting/brick_slab"


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


def test_recipe_manager_focus_matches_tag_inputs() -> None:
    _require_recipe_source()
    registry = recipe_manager.get_ingredient_registry("26.2")
    if not registry.resolve_tag("tag:minecraft:planks"):
        pytest.skip("Tag data is not available in the local jar")

    results = (
        recipe_manager.lookup("26.2")
        .focus("oak planks", RecipeIngredientRole.INPUT)
        .limit(10)
        .all()
    )
    assert results
    assert any(
        any(part.item_id.startswith("tag:") for part in recipe.inputs) for recipe in results
    )


def test_vanilla_provider_skips_unsupported_recipes() -> None:
    provider = VanillaJarProvider()
    result = provider.load("missing-version-xyz")
    assert result.recipes == []
    assert result.skipped == []
