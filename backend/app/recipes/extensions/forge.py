from __future__ import annotations

from app.parser.recipe_types import CRAFTING_SHAPED, CRAFTING_SHAPELESS, normalize_recipe_type
from app.recipes.extensions.base import CategoryExtension
from app.recipes.models import Recipe

_FORGE_TYPE_ALIASES: dict[str, str] = {
    "ore_shaped": CRAFTING_SHAPED,
    "ore_shapeless": CRAFTING_SHAPELESS,
}


class ForgeRecipeExtension:
    def matches(self, raw_type: str) -> bool:
        return normalize_recipe_type(raw_type) in _FORGE_TYPE_ALIASES

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
        canonical_type = _FORGE_TYPE_ALIASES[normalize_recipe_type(raw_type)]
        from app.recipes.parsers.json_recipe_parser import JsonRecipeParser

        return JsonRecipeParser()._parse_recipe(
            recipe_id,
            data,
            canonical_type=canonical_type,
            raw_type=raw_type,
            source=source,
            mod_id=mod_id,
        )

    def skip_reason(self, data: dict[str, object]) -> str | None:
        return None


def forge_recipe_extension() -> CategoryExtension:
    return ForgeRecipeExtension()
