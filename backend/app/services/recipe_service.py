from __future__ import annotations

from app.recipes.manager import recipe_manager
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.schemas.recipe_file import RecipeSummary

_vanilla_provider = VanillaJarProvider()


def _resolve_vanilla_jar_path(version: str):
    return _vanilla_provider.resolve_jar_path(version)


class RecipeService:
    def search_recipes(
        self,
        version: str = "26.2",
        query: str | None = None,
        uses_item: str | None = None,
        produces_item: str | None = None,
        limit: int = 50,
        include_mods: bool = True,
    ) -> list[RecipeSummary]:
        return recipe_manager.search_summaries(
            version,
            query=query,
            uses_item=uses_item,
            produces_item=produces_item,
            limit=limit,
            include_mods=include_mods,
        )

    def get_recipes(self, version: str, *, include_mods: bool = True) -> tuple[RecipeSummary, ...]:
        from app.recipes.adapters import to_recipe_summary

        recipes = recipe_manager.get_version_recipes(version, include_mods=include_mods)
        return tuple(to_recipe_summary(recipe) for recipe in recipes)


recipe_service = RecipeService()
