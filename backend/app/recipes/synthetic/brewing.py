from __future__ import annotations

import json
from pathlib import Path

from app.parser.recipe_types import BREWING
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType

_DATA_PATH = Path(__file__).parent / "data" / "brewing.json"
_BREWING_TICKS = 400


def build_brewing_recipes(*, source: str) -> list[Recipe]:
    entries = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    recipes: list[Recipe] = []

    for entry in entries:
        recipe_id = f"minecraft:synthetic/brewing/{entry['id']}"
        recipes.append(
            Recipe(
                id=recipe_id,
                recipe_type=RecipeType.BREWING,
                category_id="minecraft:brewing",
                catalyst_id="minecraft:brewing_stand",
                inputs=[
                    RecipeIO(item_id=entry["base"], amount=1.0),
                    RecipeIO(item_id=entry["ingredient"], amount=1.0),
                ],
                outputs=[RecipeIO(item_id=entry["output"], amount=1.0)],
                duration_ticks=_BREWING_TICKS,
                source=source,
                mod_id="minecraft",
                raw_type=f"minecraft:{BREWING}",
            )
        )

    return recipes
