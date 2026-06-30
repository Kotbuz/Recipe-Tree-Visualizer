from __future__ import annotations

from app.parser.recipe_types import CRAFTING_SHAPED, CRAFTING_SHAPELESS, normalize_recipe_type
from app.recipes.extensions.base import CategoryExtension
from app.recipes.models import Recipe

_FORGE_TYPE_ALIASES: dict[str, str] = {
    "ore_shaped": CRAFTING_SHAPED,
    "ore_shapeless": CRAFTING_SHAPELESS,
}


class ForgeRecipeExtension:
    @staticmethod
    def canonical_type_for(raw_type: str) -> str | None:
        return _FORGE_TYPE_ALIASES.get(normalize_recipe_type(raw_type))

    def matches(self, raw_type: str) -> bool:
        return self.canonical_type_for(raw_type) is not None

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        return None

    def skip_reason(self, data: dict[str, object]) -> str | None:
        return None


def forge_recipe_extension() -> CategoryExtension:
    return ForgeRecipeExtension()
