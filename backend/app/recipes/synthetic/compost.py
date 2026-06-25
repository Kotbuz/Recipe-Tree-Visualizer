from __future__ import annotations

import json
from pathlib import Path

from app.parser.recipe_types import COMPOSTING
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType

_DATA_PATH = Path(__file__).parent / "data" / "compostables.json"


def build_compost_recipes(*, source: str) -> list[Recipe]:
    compostables: dict[str, float] = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    recipes: list[Recipe] = []

    for item_id, chance in compostables.items():
        recipe_key = item_id.replace(":", "/")
        recipes.append(
            Recipe(
                id=f"minecraft:synthetic/compost/{recipe_key}",
                recipe_type=RecipeType.COMPOSTING,
                category_id="minecraft:composting",
                catalyst_id="minecraft:composter",
                inputs=[RecipeIO(item_id=item_id, amount=1.0)],
                outputs=[
                    RecipeIO(
                        item_id="minecraft:bone_meal",
                        amount=1.0,
                        chance=chance,
                    )
                ],
                duration_ticks=None,
                source=source,
                mod_id="minecraft",
                raw_type=f"minecraft:{COMPOSTING}",
            )
        )

    return recipes
