from __future__ import annotations

from collections import Counter

from app.recipes.item_ref import normalize_item_ref
from app.recipes.models import Recipe, RecipeIO

_AIR_ITEM_ID = "minecraft:air"


def aggregate_recipe_ios(parts: list[RecipeIO]) -> list[RecipeIO]:
    counts: Counter[tuple[str, int | None]] = Counter()
    for part in parts:
        item_id, metadata = normalize_item_ref(part.item_id, part.metadata)
        if item_id == _AIR_ITEM_ID:
            continue
        counts[(item_id, metadata)] += part.amount

    return [
        RecipeIO(item_id=item_id, amount=float(amount), metadata=metadata)
        for (item_id, metadata), amount in counts.items()
    ]


def normalize_recipe(recipe: Recipe) -> Recipe | None:
    inputs = aggregate_recipe_ios(recipe.inputs)
    outputs = aggregate_recipe_ios(recipe.outputs)
    if not inputs or not outputs:
        return None

    if inputs == recipe.inputs and outputs == recipe.outputs:
        return recipe

    return Recipe(
        id=recipe.id,
        recipe_type=recipe.recipe_type,
        category_id=recipe.category_id,
        catalyst_id=recipe.catalyst_id,
        inputs=inputs,
        outputs=outputs,
        duration_ticks=recipe.duration_ticks,
        source=recipe.source,
        mod_id=recipe.mod_id,
        raw_type=recipe.raw_type,
    )
