from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.parser.minecraft_version import mod_supports_game_version
from app.parser.models import RawModMeta
from app.recipes.adapters import item_id_to_display_name, to_recipe_summary, _display_name_for_part
from app.recipes.focus import RecipeIngredientRole
from app.recipes.item_ref import normalize_item_ref, parse_item_needle
from app.recipes.models import ProviderResult, Recipe, RecipeIO
from app.recipes.providers.mod_jar import ModJarProvider
from app.recipes.providers.synthetic import SyntheticProvider
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.loaders.recipe_paths import recipe_layout_for_version
from app.services.jvm_recipe_export_service import jvm_recipe_export_service
from app.recipes.registry import IngredientRegistry, get_version_ingredient_registry
from app.recipes.types import RecipeType
from app.schemas.recipe_file import RecipeSummary
from app.services.item_matching import items_match

_default_vanilla_provider = VanillaJarProvider()
_default_mod_provider = ModJarProvider()
_default_synthetic_provider = SyntheticProvider()


@lru_cache(maxsize=8)
def _load_vanilla_version_recipes(version: str) -> tuple[Recipe, ...]:
    if recipe_layout_for_version(version) == "jvm":
        jvm_recipe_export_service.ensure_exported(version)
        from app.services.jvm_export_status_service import recipe_export_status_service

        recipe_export_status_service.log_warnings(version)
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
        version: str | None = None,
    ) -> None:
        self._recipes = recipes
        self._ingredient_registry = ingredient_registry
        self._version = version

    def focus(
        self,
        item_id: str,
        role: RecipeIngredientRole,
        metadata: int | None = None,
    ) -> RecipeLookup:
        needle_base, needle_meta = parse_item_needle(item_id, metadata)
        needle = needle_base.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes, self._ingredient_registry, self._version)

        filtered: list[Recipe] = []
        for recipe in self._recipes:
            parts = recipe.inputs if role == RecipeIngredientRole.INPUT else recipe.outputs
            if any(self._io_matches(needle, part, needle_meta) for part in parts):
                filtered.append(recipe)

        return RecipeLookup(tuple(filtered), self._ingredient_registry, self._version)

    def query(self, text: str) -> RecipeLookup:
        needle_base, needle_meta = parse_item_needle(text, None)
        needle = needle_base.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes, self._ingredient_registry, self._version)

        filtered = [
            recipe
            for recipe in self._recipes
            if any(
                self._text_matches_part(needle, part, needle_meta)
                for part in recipe.outputs
            )
        ]
        return RecipeLookup(tuple(filtered), self._ingredient_registry, self._version)

    def _text_matches_part(
        self,
        needle: str,
        part: RecipeIO,
        metadata: int | None,
    ) -> bool:
        item_id, part_metadata = normalize_item_ref(part.item_id, part.metadata)
        if metadata is not None:
            normalized_part_meta = 0 if part_metadata is None else part_metadata
            if normalized_part_meta != metadata:
                return False

        display_name = _display_name_for_part(
            item_id,
            metadata=part_metadata,
            version=self._version,
        ).lower()
        if needle in display_name or needle in item_id.lower():
            return True
        return self._ingredient_matches(needle, item_id)

    def limit(self, count: int) -> RecipeLookup:
        if count <= 0:
            return RecipeLookup((), self._ingredient_registry, self._version)
        return RecipeLookup(self._recipes[:count], self._ingredient_registry, self._version)

    def all(self) -> list[Recipe]:
        return list(self._recipes)

    def summaries(self) -> list[RecipeSummary]:
        return [
            to_recipe_summary(
                recipe,
                ingredient_registry=self._ingredient_registry,
                version=self._version,
            )
            for recipe in self._recipes
        ]

    def _io_matches(self, needle: str, part: RecipeIO, metadata: int | None) -> bool:
        item_id, part_metadata = normalize_item_ref(part.item_id, part.metadata)
        if metadata is not None:
            normalized_part_meta = 0 if part_metadata is None else part_metadata
            if normalized_part_meta != metadata:
                return False

        if self._ingredient_matches(needle, item_id):
            return True

        if self._version is not None:
            display_name = _display_name_for_part(
                item_id,
                metadata=part_metadata,
                version=self._version,
            )
            if items_match(needle, display_name.lower()):
                return True

        return False

    def _ingredient_matches(self, needle: str, item_id: str) -> bool:
        if self._ingredient_registry is not None:
            return self._ingredient_registry.ingredient_matches(needle, item_id)
        return RecipeLookup._fallback_ingredient_matches(needle, item_id)

    @staticmethod
    def _fallback_ingredient_matches(needle: str, item_id: str) -> bool:
        display_name = item_id_to_display_name(item_id)
        return items_match(needle, display_name) or items_match(needle, item_id)


@dataclass(frozen=True)
class _ModLoad:
    jar_path: str
    meta: RawModMeta
    recipes: dict[str, Recipe]
    storage_version: str


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
        self._mod_loads: dict[str, _ModLoad] = {}

    @property
    def mod_jar_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._mod_loads))

    def mod_jar_paths_for_version(self, version: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                jar_path
                for jar_path, load in self._mod_loads.items()
                if load.storage_version == version
            )
        )

    def load_mod_jar(
        self,
        jar_path: str,
        *,
        meta: RawModMeta,
        storage_version: str,
    ) -> ProviderResult:
        result = self._mod_provider.load(jar_path, version=storage_version)
        resolved = str(Path(jar_path).resolve())
        recipes = {recipe.id: recipe for recipe in result.recipes}
        self._mod_loads[resolved] = _ModLoad(
            jar_path=resolved,
            meta=meta,
            recipes=recipes,
            storage_version=storage_version,
        )
        self._clear_caches()
        return result

    def clear_mods(self) -> None:
        self._mod_loads.clear()
        self._clear_caches()

    def clear_mods_for_version(self, version: str) -> None:
        to_remove = [
            jar_path
            for jar_path, load in self._mod_loads.items()
            if load.storage_version == version
        ]
        for jar_path in to_remove:
            del self._mod_loads[jar_path]
        if to_remove:
            self._clear_caches()

    def get_mod_recipes(self, version: str | None = None) -> tuple[Recipe, ...]:
        if version is None:
            return tuple(
                recipe for load in self._mod_loads.values() for recipe in load.recipes.values()
            )
        return self._mod_recipes_for_version(version)

    def _mod_recipes_for_version(self, version: str) -> tuple[Recipe, ...]:
        recipes: list[Recipe] = []
        for load in self._mod_loads.values():
            if load.storage_version == version:
                recipes.extend(load.recipes.values())
        return tuple(recipes)

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

        if include_mods:
            for recipe in self._mod_recipes_for_version(version):
                merged[recipe.id] = recipe

        return tuple(merged.values())

    def lookup(
        self,
        version: str,
        recipe_type: RecipeType | None = None,
        *,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> RecipeLookup:
        from app.services.mod_service import mod_service

        if include_mods:
            mod_service.ensure_version_mods_loaded(version)

        recipes = self.get_version_recipes(
            version,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
        )
        registry = get_version_ingredient_registry(version)
        if recipe_type is None:
            return RecipeLookup(recipes, registry, version)
        filtered = tuple(recipe for recipe in recipes if recipe.recipe_type == recipe_type)
        return RecipeLookup(filtered, registry, version)

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
        focus_metadata: int | None = None,
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
            lookup = lookup.focus(normalized_focus_item, focus_role, focus_metadata)
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
        from app.recipes.loaders.item_catalog_loader import _parse_ae2_lang, load_item_catalog

        load_item_catalog.cache_clear()
        _parse_ae2_lang.cache_clear()


recipe_manager = RecipeManager()
