from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.recipes.adapters import item_id_to_display_name, to_recipe_summary
from app.recipes.focus import RecipeIngredientRole
from app.recipes.models import ProviderResult, Recipe
from app.recipes.providers.mod_jar import ModJarProvider
from app.recipes.providers.synthetic import SyntheticProvider
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.registry import IngredientRegistry, get_version_ingredient_registry
from app.recipes.types import RecipeType
from app.schemas.recipe_file import RecipeSummary
from app.services.item_matching import items_match

_default_vanilla_provider = VanillaJarProvider()
_default_mod_provider = ModJarProvider()
_default_synthetic_provider = SyntheticProvider()


@lru_cache(maxsize=8)
def _load_vanilla_version_recipes(version: str) -> tuple[Recipe, ...]:
    result = _default_vanilla_provider.load(version)
    return tuple(result.recipes)


@lru_cache(maxsize=8)
def _load_synthetic_version_recipes(version: str) -> tuple[Recipe, ...]:
    result = _default_synthetic_provider.load(version)
    return tuple(result.recipes)


class RecipeLookup:
    def __init__(
        self,
        recipes: tuple[Recipe, ...],
        ingredient_registry: IngredientRegistry | None = None,
    ) -> None:
        self._recipes = recipes
        self._ingredient_registry = ingredient_registry

    def focus(self, item_id: str, role: RecipeIngredientRole) -> RecipeLookup:
        needle = item_id.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes, self._ingredient_registry)

        filtered: list[Recipe] = []
        for recipe in self._recipes:
            parts = recipe.inputs if role == RecipeIngredientRole.INPUT else recipe.outputs
            if any(self._ingredient_matches(needle, part.item_id) for part in parts):
                filtered.append(recipe)

        return RecipeLookup(tuple(filtered), self._ingredient_registry)

    def query(self, text: str) -> RecipeLookup:
        needle = text.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes, self._ingredient_registry)

        filtered = [
            recipe
            for recipe in self._recipes
            if any(needle in item_id_to_display_name(part.item_id).lower() for part in recipe.outputs)
        ]
        return RecipeLookup(tuple(filtered), self._ingredient_registry)

    def limit(self, count: int) -> RecipeLookup:
        if count <= 0:
            return RecipeLookup((), self._ingredient_registry)
        return RecipeLookup(self._recipes[:count], self._ingredient_registry)

    def all(self) -> list[Recipe]:
        return list(self._recipes)

    def summaries(self) -> list[RecipeSummary]:
        return [to_recipe_summary(recipe) for recipe in self._recipes]

    def _ingredient_matches(self, needle: str, item_id: str) -> bool:
        if self._ingredient_registry is not None:
            return self._ingredient_registry.ingredient_matches(needle, item_id)
        return RecipeLookup._fallback_ingredient_matches(needle, item_id)

    @staticmethod
    def _fallback_ingredient_matches(needle: str, item_id: str) -> bool:
        display_name = item_id_to_display_name(item_id)
        return items_match(needle, display_name) or items_match(needle, item_id)


class RecipeManager:
    def __init__(
        self,
        vanilla_provider: VanillaJarProvider | None = None,
        mod_provider: ModJarProvider | None = None,
        synthetic_provider: SyntheticProvider | None = None,
    ) -> None:
        self._vanilla_provider = vanilla_provider or _default_vanilla_provider
        self._mod_provider = mod_provider or _default_mod_provider
        self._synthetic_provider = synthetic_provider or _default_synthetic_provider
        self._mod_recipes: dict[str, Recipe] = {}
        self._mod_jar_paths: tuple[str, ...] = ()

    @property
    def mod_jar_paths(self) -> tuple[str, ...]:
        return self._mod_jar_paths

    def load_mod_jar(self, jar_path: str) -> ProviderResult:
        result = self._mod_provider.load(jar_path)
        for recipe in result.recipes:
            self._mod_recipes[recipe.id] = recipe

        paths = set(self._mod_jar_paths)
        paths.add(str(Path(jar_path).resolve()))
        self._mod_jar_paths = tuple(sorted(paths))
        self._clear_caches()
        return result

    def clear_mods(self) -> None:
        self._mod_recipes.clear()
        self._mod_jar_paths = ()
        self._clear_caches()

    def get_mod_recipes(self) -> tuple[Recipe, ...]:
        return tuple(self._mod_recipes.values())

    def get_version_recipes(
        self,
        version: str,
        *,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> tuple[Recipe, ...]:
        merged: dict[str, Recipe] = {
            recipe.id: recipe for recipe in self._load_vanilla_recipes(version)
        }

        if include_synthetic:
            for recipe in self._load_synthetic_recipes(version):
                merged[recipe.id] = recipe

        if include_mods and self._mod_recipes:
            merged.update(self._mod_recipes)

        return tuple(merged.values())

    def lookup(
        self,
        version: str,
        recipe_type: RecipeType | None = None,
        *,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> RecipeLookup:
        recipes = self.get_version_recipes(
            version,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
        )
        registry = get_version_ingredient_registry(version)
        if recipe_type is None:
            return RecipeLookup(recipes, registry)
        filtered = tuple(recipe for recipe in recipes if recipe.recipe_type == recipe_type)
        return RecipeLookup(filtered, registry)

    def get_ingredient_registry(self, version: str) -> IngredientRegistry:
        return get_version_ingredient_registry(version)

    def search_summaries(
        self,
        version: str,
        *,
        query: str | None = None,
        uses_item: str | None = None,
        produces_item: str | None = None,
        focus_item: str | None = None,
        focus_role: RecipeIngredientRole | None = None,
        limit: int = 50,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> list[RecipeSummary]:
        lookup = self.lookup(
            version,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
        )
        normalized_query = query.strip() if query else ""
        normalized_uses_item = uses_item.strip() if uses_item else ""
        normalized_produces_item = produces_item.strip() if produces_item else ""
        normalized_focus_item = focus_item.strip() if focus_item else ""

        if (
            not normalized_query
            and not normalized_uses_item
            and not normalized_produces_item
            and not normalized_focus_item
        ):
            return []

        if normalized_focus_item and focus_role is not None:
            lookup = lookup.focus(normalized_focus_item, focus_role)
        else:
            if normalized_uses_item:
                lookup = lookup.focus(normalized_uses_item, RecipeIngredientRole.INPUT)
            if normalized_produces_item:
                lookup = lookup.focus(normalized_produces_item, RecipeIngredientRole.OUTPUT)

        if normalized_query:
            lookup = lookup.query(normalized_query)

        return lookup.limit(limit).summaries()

    def _load_vanilla_recipes(self, version: str) -> tuple[Recipe, ...]:
        if self._vanilla_provider is _default_vanilla_provider:
            return _load_vanilla_version_recipes(version)
        return tuple(self._vanilla_provider.load(version).recipes)

    def _load_synthetic_recipes(self, version: str) -> tuple[Recipe, ...]:
        if self._synthetic_provider is _default_synthetic_provider:
            return _load_synthetic_version_recipes(version)
        return tuple(self._synthetic_provider.load(version).recipes)

    @staticmethod
    def _clear_caches() -> None:
        _load_vanilla_version_recipes.cache_clear()
        _load_synthetic_version_recipes.cache_clear()
        get_version_ingredient_registry.cache_clear()


recipe_manager = RecipeManager()
