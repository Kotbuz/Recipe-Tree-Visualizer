from __future__ import annotations

from app.parser.recipe_types import normalize_recipe_type
from app.recipes.extensions.base import CategoryExtension
from app.recipes.extensions.recipe_fluids import item_io_from_ingredient, result_io_from_payload
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType

_CREATE_FILLING = "create:filling"


class CreateExtension:
    def matches(self, raw_type: str) -> bool:
        return normalize_recipe_type(raw_type) == _CREATE_FILLING

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        ingredients = data.get("ingredients")
        if not isinstance(ingredients, list):
            return None

        inputs: list[RecipeIO] = []
        for ingredient in ingredients:
            parsed = item_io_from_ingredient(ingredient)
            if parsed is not None:
                inputs.append(parsed)

        results = data.get("results")
        if isinstance(results, list) and results:
            output = result_io_from_payload(results[0])
        else:
            output = result_io_from_payload(data.get("result"))

        if not inputs or output is None:
            return None

        return Recipe(
            id=recipe_id,
            recipe_type=RecipeType.CRAFTING_SHAPELESS,
            category_id="create:filling",
            catalyst_id="create:spout",
            inputs=inputs,
            outputs=[output],
            duration_ticks=None,
            source=source,
            mod_id=mod_id or "create",
            raw_type=str(data.get("type", _CREATE_FILLING)),
        )

    def skip_reason(self, data: dict[str, object]) -> str | None:
        return None

    def display_name(self, raw_type: str) -> str | None:
        if normalize_recipe_type(raw_type) == _CREATE_FILLING:
            return "Create Spout"
        return None


def create_extension() -> CategoryExtension:
    return CreateExtension()
