from __future__ import annotations

from app.parser.recipe_types import normalize_recipe_type
from app.recipes.extensions.base import CategoryExtension
from app.recipes.extensions.recipe_fluids import (
    result_io_from_payload,
    shaped_inputs_from_pattern,
)
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType

_FLUID_RECIPE_TYPES = frozenset(
    {
        "immersiveengineering:shaped_fluid",
        "immersiveengineering:shapeless_fluid",
    }
)
_DISPLAY_NAMES: dict[str, str] = {
    "immersiveengineering:shaped_fluid": "Immersive Engineering",
    "immersiveengineering:shapeless_fluid": "Immersive Engineering",
}


class ImmersiveEngineeringExtension:
    def matches(self, raw_type: str) -> bool:
        return normalize_recipe_type(raw_type) in _FLUID_RECIPE_TYPES

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        raw_type = data.get("type")
        if not isinstance(raw_type, str):
            return None

        normalized = normalize_recipe_type(raw_type)
        if normalized == "immersiveengineering:shaped_fluid":
            return self._parse_shaped_fluid(
                recipe_id,
                data,
                raw_type=raw_type,
                source=source,
                mod_id=mod_id,
            )
        if normalized == "immersiveengineering:shapeless_fluid":
            return self._parse_shapeless_fluid(
                recipe_id,
                data,
                raw_type=raw_type,
                source=source,
                mod_id=mod_id,
            )
        return None

    def skip_reason(self, data: dict[str, object]) -> str | None:
        return None

    def display_name(self, raw_type: str) -> str | None:
        return _DISPLAY_NAMES.get(normalize_recipe_type(raw_type))

    def _parse_shaped_fluid(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        raw_type: str,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        inputs = shaped_inputs_from_pattern(data.get("pattern"), data.get("key"))
        output = result_io_from_payload(data.get("result"))
        if not inputs or output is None:
            return None

        return Recipe(
            id=recipe_id,
            recipe_type=RecipeType.CRAFTING_SHAPED,
            category_id="immersiveengineering:crafting",
            catalyst_id="immersiveengineering:workbench",
            inputs=inputs,
            outputs=[output],
            duration_ticks=None,
            source=source,
            mod_id=mod_id or "immersiveengineering",
            raw_type=raw_type,
        )

    def _parse_shapeless_fluid(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        raw_type: str,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        from app.recipes.extensions.recipe_fluids import item_io_from_ingredient

        ingredients = data.get("ingredients")
        if not isinstance(ingredients, list):
            return None

        inputs: list[RecipeIO] = []
        for ingredient in ingredients:
            parsed = item_io_from_ingredient(ingredient)
            if parsed is not None:
                inputs.append(parsed)

        output = result_io_from_payload(data.get("result"))
        if not inputs or output is None:
            return None

        return Recipe(
            id=recipe_id,
            recipe_type=RecipeType.CRAFTING_SHAPELESS,
            category_id="immersiveengineering:crafting",
            catalyst_id="immersiveengineering:workbench",
            inputs=inputs,
            outputs=[output],
            duration_ticks=None,
            source=source,
            mod_id=mod_id or "immersiveengineering",
            raw_type=raw_type,
        )


def immersive_engineering_extension() -> CategoryExtension:
    return ImmersiveEngineeringExtension()
