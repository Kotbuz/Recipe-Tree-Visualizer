from __future__ import annotations

from functools import lru_cache

from app.recipes.adapters import item_id_to_display_name, to_recipe_summary
from app.recipes.focus import RecipeIngredientRole
from app.recipes.models import Recipe
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.types import RecipeType
from app.schemas.recipe_file import RecipeSummary
from app.services.item_matching import items_match

_default_vanilla_provider = VanillaJarProvider()


@lru_cache(maxsize=8)
def _load_default_version_recipes(version: str) -> tuple[Recipe, ...]:
    result = _default_vanilla_provider.load(version)
    return tuple(result.recipes)


class RecipeLookup:
    def __init__(self, recipes: tuple[Recipe, ...]) -> None:
        self._recipes = recipes

    def focus(self, item_id: str, role: RecipeIngredientRole) -> RecipeLookup:
        needle = item_id.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes)

        filtered: list[Recipe] = []
        for recipe in self._recipes:
            parts = recipe.inputs if role == RecipeIngredientRole.INPUT else recipe.outputs
            if any(self._ingredient_matches(needle, part.item_id) for part in parts):
                filtered.append(recipe)

        return RecipeLookup(tuple(filtered))

    def query(self, text: str) -> RecipeLookup:
        needle = text.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes)

        filtered = [
            recipe
            for recipe in self._recipes
            if any(needle in item_id_to_display_name(part.item_id).lower() for part in recipe.outputs)
        ]
        return RecipeLookup(tuple(filtered))

    def limit(self, count: int) -> RecipeLookup:
        if count <= 0:
            return RecipeLookup(())
        return RecipeLookup(self._recipes[:count])

    def all(self) -> list[Recipe]:
        return list(self._recipes)

    def summaries(self) -> list[RecipeSummary]:
        return [to_recipe_summary(recipe) for recipe in self._recipes]

    @staticmethod
    def _ingredient_matches(needle: str, item_id: str) -> bool:
        display_name = item_id_to_display_name(item_id)
        return items_match(needle, display_name) or items_match(needle, item_id)


class RecipeManager:
    def __init__(self, vanilla_provider: VanillaJarProvider | None = None) -> None:
        self._vanilla_provider = vanilla_provider or _default_vanilla_provider

    def get_version_recipes(self, version: str) -> tuple[Recipe, ...]:
        if self._vanilla_provider is _default_vanilla_provider:
            return _load_default_version_recipes(version)
        return tuple(self._vanilla_provider.load(version).recipes)

    def lookup(self, version: str, recipe_type: RecipeType | None = None) -> RecipeLookup:
        recipes = self.get_version_recipes(version)
        if recipe_type is None:
            return RecipeLookup(recipes)
        filtered = tuple(recipe for recipe in recipes if recipe.recipe_type == recipe_type)
        return RecipeLookup(filtered)

    def search_summaries(
        self,
        version: str,
        *,
        query: str | None = None,
        uses_item: str | None = None,
        produces_item: str | None = None,
        limit: int = 50,
    ) -> list[RecipeSummary]:
        lookup = self.lookup(version)
        normalized_query = query.strip() if query else ""
        normalized_uses_item = uses_item.strip() if uses_item else ""
        normalized_produces_item = produces_item.strip() if produces_item else ""

        if not normalized_query and not normalized_uses_item and not normalized_produces_item:
            return []

        if normalized_uses_item:
            lookup = lookup.focus(normalized_uses_item, RecipeIngredientRole.INPUT)
        if normalized_produces_item:
            lookup = lookup.focus(normalized_produces_item, RecipeIngredientRole.OUTPUT)
        if normalized_query:
            lookup = lookup.query(normalized_query)

        return lookup.limit(limit).summaries()


recipe_manager = RecipeManager()
