from app.recipes.models import RecipeIO
from app.recipes.recipe_io_utils import aggregate_recipe_ios, normalize_recipe
from app.recipes.types import RecipeType


def test_aggregate_recipe_ios_merges_duplicates() -> None:
    parts = [
        RecipeIO(item_id="minecraft:stick", amount=1.0),
        RecipeIO(item_id="minecraft:stick", amount=1.0),
        RecipeIO(
            item_id="appliedenergistics2:item.ItemMultiMaterial",
            amount=1.0,
            metadata=0,
        ),
        RecipeIO(
            item_id="appliedenergistics2:item.ItemMultiMaterial",
            amount=1.0,
            metadata=0,
        ),
        RecipeIO(
            item_id="appliedenergistics2:item.ItemMultiMaterial",
            amount=1.0,
            metadata=0,
        ),
    ]

    merged = aggregate_recipe_ios(parts)

    assert len(merged) == 2
    assert merged[0].amount == 2.0
    assert merged[1].amount == 3.0


def test_aggregate_recipe_ios_filters_air() -> None:
    parts = [
        RecipeIO(item_id="minecraft:air", amount=2.0),
        RecipeIO(item_id="minecraft:planks", amount=2.0),
    ]

    merged = aggregate_recipe_ios(parts)

    assert len(merged) == 1
    assert merged[0].item_id == "minecraft:planks"
    assert merged[0].amount == 2.0


def test_normalize_recipe_drops_air_only_inputs() -> None:
    from app.recipes.models import Recipe

    recipe = Recipe(
        id="minecraft:stick",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="crafting_shaped",
        catalyst_id="minecraft:crafting_table",
        inputs=[RecipeIO(item_id="minecraft:air", amount=2.0)],
        outputs=[RecipeIO(item_id="minecraft:stick", amount=4.0)],
        duration_ticks=None,
        source="test",
        mod_id="minecraft",
        raw_type="forge:ore_shaped",
    )

    assert normalize_recipe(recipe) is None
