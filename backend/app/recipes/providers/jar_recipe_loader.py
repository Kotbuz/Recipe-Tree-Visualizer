from __future__ import annotations

import re

from app.recipes.models import ProviderResult, SkippedRecipe
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser

RECIPE_PATH = re.compile(r"^data/([^/]+)/recipes?/(.+\.json)$")
ADVANCEMENT_SEGMENT = "/advancement/"


def try_add_recipe(
    parser: JsonRecipeParser,
    result: ProviderResult,
    recipe_id: str,
    data: dict[str, object],
    *,
    source: str,
    mod_id: str,
) -> None:
    raw_type = data.get("type")
    if not parser.can_parse(data):
        result.skipped.append(
            SkippedRecipe(
                recipe_id=recipe_id,
                raw_type=raw_type if isinstance(raw_type, str) else None,
                reason="unsupported or invalid recipe",
            )
        )
        return

    recipe = parser.parse(recipe_id, data, source=source, mod_id=mod_id)
    if recipe is None:
        result.skipped.append(
            SkippedRecipe(
                recipe_id=recipe_id,
                raw_type=raw_type if isinstance(raw_type, str) else None,
                reason="parse failed",
            )
        )
        return

    result.recipes.append(recipe)
