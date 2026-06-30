from __future__ import annotations

from app.recipes.focus import RecipeIngredientRole
from app.recipes.manager import recipe_manager
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.schemas.recipe_file import RecipeSummary

_vanilla_provider = VanillaJarProvider()


def _resolve_vanilla_jar_path(version: str):
    return _vanilla_provider.resolve_jar_path(version)


def _parse_focus_role(raw: str | None) -> RecipeIngredientRole | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized == RecipeIngredientRole.INPUT.value:
        return RecipeIngredientRole.INPUT
    if normalized == RecipeIngredientRole.OUTPUT.value:
        return RecipeIngredientRole.OUTPUT
    return None


class RecipeService:
    def search_recipes(
        self,
        version: str = "26.2",
        profile_id: str | None = None,
        query: str | None = None,
        uses_item: str | None = None,
        produces_item: str | None = None,
        focus_item: str | None = None,
        focus_role: str | None = None,
        focus_metadata: int | None = None,
        limit: int = 50,
        include_mods: bool = True,
    ) -> list[RecipeSummary]:
        return recipe_manager.search_summaries(
            version,
            profile_id=profile_id,
            query=query,
            uses_item=uses_item,
            produces_item=produces_item,
            focus_item=focus_item,
            focus_role=_parse_focus_role(focus_role),
            focus_metadata=focus_metadata,
            limit=limit,
            include_mods=include_mods,
        )

    def get_recipes(self, version: str, *, include_mods: bool = True) -> tuple[RecipeSummary, ...]:
        from app.recipes.adapters import to_recipe_summary
        from app.recipes.registry import get_version_ingredient_registry

        recipes = recipe_manager.get_version_recipes(version, include_mods=include_mods)
        registry = get_version_ingredient_registry(version)
        return tuple(to_recipe_summary(recipe, ingredient_registry=registry) for recipe in recipes)


recipe_service = RecipeService()
