from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.parser.minecraft_version import mod_supports_game_version
from app.parser.models import RawModMeta
from app.recipes.adapters import item_id_to_display_name, to_recipe_summary, _display_name_for_part
from app.recipes.focus import RecipeIngredientRole
from app.recipes.ingredient import IngredientKind
from app.recipes.item_ref import normalize_item_ref, parse_item_needle
from app.recipes.models import ProviderResult, Recipe, RecipeIO
from app.recipes.providers.mod_jar import ModJarProvider
from app.recipes.providers.synthetic import SyntheticProvider
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.loaders.recipe_paths import recipe_layout_for_version
from app.services.jvm_recipe_export_service import jvm_recipe_export_service
from app.recipes.registry import (
    IngredientRegistry,
    get_profile_ingredient_registry,
    get_version_ingredient_registry,
)
from app.recipes.types import RecipeType
from app.schemas.recipe_file import RecipeSummary
from app.services.item_matching import items_match
from app.services.profile_storage import profile_storage_key
from app.services.version_service import version_service


def resolve_recipe_scope(
    version: str,
    profile_id: str | None = None,
) -> tuple[str, str, str]:
    """Возвращает (mc_version, profile_id, storage_key)."""
    resolved_profile = version_service._resolve_profile_id(version, profile_id)
    return version, resolved_profile, profile_storage_key(version, resolved_profile)

_default_vanilla_provider = VanillaJarProvider()
_default_mod_provider = ModJarProvider()
_default_synthetic_provider = SyntheticProvider()


@lru_cache(maxsize=32)
def _load_vanilla_version_recipes(mc_version: str, profile_id: str) -> tuple[Recipe, ...]:
    if recipe_layout_for_version(mc_version) == "jvm":
        jvm_recipe_export_service.ensure_exported(mc_version, profile_id=profile_id)
        from app.services.jvm_export_status_service import recipe_export_status_service

        recipe_export_status_service.log_warnings(mc_version, profile_id=profile_id)
    result = _default_vanilla_provider.load(mc_version, profile_id=profile_id)
    return tuple(result.recipes)


@lru_cache(maxsize=8)
def _load_synthetic_version_recipes(version: str) -> tuple[Recipe, ...]:
    result = _default_synthetic_provider.load(version)
    return tuple(result.recipes)


@dataclass(frozen=True)
class _VersionRecipeBundle:
    recipes: tuple[Recipe, ...]
    recipes_by_id: dict[str, Recipe]
    input_ids_by_key: dict[str, frozenset[str]]
    output_ids_by_key: dict[str, frozenset[str]]


def _part_index_keys(
    item_id: str,
    *,
    metadata: int | None = None,
    version: str | None = None,
) -> frozenset[str]:
    keys: set[str] = set()
    normalized = item_id.strip().lower()
    if not normalized:
        return frozenset()

    keys.add(normalized)
    if ":" in normalized:
        keys.add(normalized.split(":", 1)[1])

    keys.add(item_id_to_display_name(item_id).lower())

    if version is not None:
        from app.recipes.legacy_item_icons import resolve_legacy_display_name
        from app.recipes.loaders.item_catalog_loader import resolve_catalog_display_name

        catalog_name = resolve_catalog_display_name(item_id, metadata, version=version)
        if catalog_name:
            keys.add(catalog_name.lower())
        legacy_name = resolve_legacy_display_name(item_id, metadata, version=version)
        if legacy_name:
            keys.add(legacy_name.lower())

    return frozenset(key for key in keys if key)


def _focus_lookup_keys(needle: str) -> tuple[str, ...]:
    normalized = needle.strip().lower()
    if not normalized:
        return ()
    keys = {normalized}
    if ":" in normalized:
        keys.add(normalized.split(":", 1)[1])
    return tuple(keys)


def _build_version_recipe_bundle(
    recipes: tuple[Recipe, ...],
    *,
    version: str | None,
) -> _VersionRecipeBundle:
    recipes_by_id = {recipe.id: recipe for recipe in recipes}
    input_ids: dict[str, set[str]] = defaultdict(set)
    output_ids: dict[str, set[str]] = defaultdict(set)

    for recipe in recipes:
        for part in recipe.inputs:
            for key in _part_index_keys(
                part.item_id,
                metadata=part.metadata,
                version=version,
            ):
                input_ids[key].add(recipe.id)
        for part in recipe.outputs:
            for key in _part_index_keys(
                part.item_id,
                metadata=part.metadata,
                version=version,
            ):
                output_ids[key].add(recipe.id)

    return _VersionRecipeBundle(
        recipes=recipes,
        recipes_by_id=recipes_by_id,
        input_ids_by_key={key: frozenset(ids) for key, ids in input_ids.items()},
        output_ids_by_key={key: frozenset(ids) for key, ids in output_ids.items()},
    )


class RecipeLookup:
    def __init__(
        self,
        recipes: tuple[Recipe, ...],
        ingredient_registry: IngredientRegistry | None = None,
        version: str | None = None,
        *,
        bundle: _VersionRecipeBundle | None = None,
    ) -> None:
        self._recipes = recipes
        self._ingredient_registry = ingredient_registry
        self._version = version
        self._bundle = bundle

    def focus(
        self,
        item_id: str,
        role: RecipeIngredientRole,
        metadata: int | None = None,
        *,
        limit: int | None = None,
    ) -> RecipeLookup:
        needle_base, needle_meta = parse_item_needle(item_id, metadata)
        needle = needle_base.strip().lower()
        if not needle:
            return RecipeLookup(
                self._recipes,
                self._ingredient_registry,
                self._version,
                bundle=self._bundle,
            )

        if self._bundle is not None:
            indexed = self._focus_via_index(needle, role, needle_meta, limit=limit)
            if indexed is not None:
                return RecipeLookup(
                    indexed,
                    self._ingredient_registry,
                    self._version,
                    bundle=self._bundle,
                )

        filtered: list[Recipe] = []
        for recipe in self._recipes:
            parts = recipe.inputs if role == RecipeIngredientRole.INPUT else recipe.outputs
            if any(self._io_matches(needle, part, needle_meta) for part in parts):
                filtered.append(recipe)
                if limit is not None and len(filtered) >= limit:
                    break

        return RecipeLookup(
            tuple(filtered),
            self._ingredient_registry,
            self._version,
            bundle=self._bundle,
        )

    def _focus_via_index(
        self,
        needle: str,
        role: RecipeIngredientRole,
        metadata: int | None,
        *,
        limit: int | None,
    ) -> tuple[Recipe, ...] | None:
        assert self._bundle is not None
        index = (
            self._bundle.output_ids_by_key
            if role == RecipeIngredientRole.OUTPUT
            else self._bundle.input_ids_by_key
        )
        candidate_ids: set[str] = set()
        for key in _focus_lookup_keys(needle):
            candidate_ids |= index.get(key, frozenset())

        if self._ingredient_registry is not None:
            candidate_ids |= self._expand_focus_candidates_via_registry(needle, index)

        if not candidate_ids:
            return None

        filtered: list[Recipe] = []
        for recipe_id in candidate_ids:
            recipe = self._bundle.recipes_by_id.get(recipe_id)
            if recipe is None:
                continue
            parts = recipe.inputs if role == RecipeIngredientRole.INPUT else recipe.outputs
            if any(self._io_matches(needle, part, metadata) for part in parts):
                filtered.append(recipe)
                if limit is not None and len(filtered) >= limit:
                    break
        if not filtered:
            return None

        return tuple(filtered)

    def _expand_focus_candidates_via_registry(
        self,
        needle: str,
        index: dict[str, frozenset[str]],
    ) -> set[str]:
        if self._ingredient_registry is None:
            return set()

        candidate_ids: set[str] = set()
        tag_id = self._ingredient_registry._needle_to_tag_id(needle)
        if tag_id:
            for member in self._ingredient_registry.resolve_tag(tag_id):
                for key in _focus_lookup_keys(member):
                    candidate_ids |= index.get(key, frozenset())
            candidate_ids |= index.get(tag_id.lower(), frozenset())
            short_tag = tag_id.rsplit(":", 1)[-1]
            candidate_ids |= index.get(short_tag, frozenset())

        for ingredient in self._ingredient_registry.search(needle, limit=32):
            for key in _focus_lookup_keys(ingredient.id):
                candidate_ids |= index.get(key, frozenset())
            if ingredient.kind == IngredientKind.TAG:
                tag_key = ingredient.id.lower()
                candidate_ids |= index.get(tag_key, frozenset())
                candidate_ids |= index.get(tag_key.rsplit(":", 1)[-1], frozenset())
        return candidate_ids

    def query(self, text: str, *, limit: int | None = None) -> RecipeLookup:
        needle_base, needle_meta = parse_item_needle(text, None)
        needle = needle_base.strip().lower()
        if not needle:
            return RecipeLookup(self._recipes, self._ingredient_registry, self._version)

        filtered: list[Recipe] = []
        for recipe in self._recipes:
            if any(
                self._text_search_matches(needle, part, needle_meta)
                for part in recipe.outputs
            ):
                filtered.append(recipe)
                if limit is not None and len(filtered) >= limit:
                    break
        return RecipeLookup(tuple(filtered), self._ingredient_registry, self._version, bundle=self._bundle)

    def _text_search_matches(
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

        item_id_lower = item_id.lower()
        if needle in item_id_lower:
            return True

        cheap_display = item_id_to_display_name(item_id).lower()
        if needle in cheap_display:
            return True

        if self._version is not None:
            from app.recipes.legacy_item_icons import resolve_legacy_display_name
            from app.recipes.loaders.item_catalog_loader import resolve_catalog_display_name

            catalog_name = resolve_catalog_display_name(
                item_id,
                part_metadata,
                version=self._version,
            )
            if catalog_name is not None and needle in catalog_name.lower():
                return True
            legacy_name = resolve_legacy_display_name(
                item_id,
                part_metadata,
                version=self._version,
            )
            if legacy_name is not None and needle in legacy_name.lower():
                return True

        if items_match(needle, cheap_display):
            return True

        if self._ingredient_registry is not None:
            alias = self._ingredient_registry.resolve_alias(cheap_display).lower()
            if items_match(needle, alias):
                return True
            if self._ingredient_registry.resolve_alias(needle) != needle:
                return self._ingredient_matches(needle, item_id)

        if item_id.startswith("tag:"):
            return self._ingredient_matches(needle, item_id)
        if ":" in needle:
            return self._ingredient_matches(needle, item_id)
        return False

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
            return RecipeLookup((), self._ingredient_registry, self._version, bundle=self._bundle)
        return RecipeLookup(
            self._recipes[:count],
            self._ingredient_registry,
            self._version,
            bundle=self._bundle,
        )

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

        item_id_lower = item_id.lower()
        cheap_display = item_id_to_display_name(item_id).lower()

        if items_match(needle, item_id_lower) or items_match(needle, cheap_display):
            return True
        if needle in item_id_lower or needle in cheap_display:
            return True

        if self._version is not None:
            from app.recipes.legacy_item_icons import resolve_legacy_display_name
            from app.recipes.loaders.item_catalog_loader import resolve_catalog_display_name

            catalog_name = resolve_catalog_display_name(
                item_id,
                part_metadata,
                version=self._version,
            )
            if catalog_name is not None and items_match(needle, catalog_name.lower()):
                return True
            legacy_name = resolve_legacy_display_name(
                item_id,
                part_metadata,
                version=self._version,
            )
            if legacy_name is not None and items_match(needle, legacy_name.lower()):
                return True

        if self._ingredient_registry is not None:
            alias = self._ingredient_registry.resolve_alias(cheap_display).lower()
            if items_match(needle, alias):
                return True

        if item_id.startswith("tag:"):
            return self._ingredient_matches(needle, item_id)
        if ":" in needle:
            return self._ingredient_matches(needle, item_id)
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
        self._version_recipe_cache: dict[tuple[str, bool, bool], tuple[Recipe, ...]] = {}
        self._version_bundle_cache: dict[tuple[str, bool, bool], _VersionRecipeBundle] = {}

    def _version_recipe_cache_key(
        self,
        version: str,
        profile_id: str | None,
        include_mods: bool,
        include_synthetic: bool,
    ) -> tuple[str, bool, bool]:
        _, _, storage_key = resolve_recipe_scope(version, profile_id)
        return storage_key, include_mods, include_synthetic

    @property
    def mod_jar_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._mod_loads))

    def mod_jar_paths_for_storage(self, storage_key: str) -> tuple[str, ...]:
        legacy_key = storage_key.split("::", 1)[0] if "::" in storage_key else None
        return tuple(
            sorted(
                jar_path
                for jar_path, load in self._mod_loads.items()
                if load.storage_version == storage_key
                or (legacy_key is not None and load.storage_version == legacy_key)
            )
        )

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
        clear_caches: bool = True,
    ) -> ProviderResult:
        result = self._mod_provider.load(
            jar_path,
            version=storage_version.split("::", 1)[0],
        )
        resolved = str(Path(jar_path).resolve())
        recipes = {recipe.id: recipe for recipe in result.recipes}
        self._mod_loads[resolved] = _ModLoad(
            jar_path=resolved,
            meta=meta,
            recipes=recipes,
            storage_version=storage_version,
        )
        self._version_recipe_cache.clear()
        if clear_caches:
            self._clear_caches()
        return result

    def get_recipe_bundle(
        self,
        version: str,
        *,
        profile_id: str | None = None,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> _VersionRecipeBundle:
        cache_key = self._version_recipe_cache_key(
            version,
            profile_id,
            include_mods,
            include_synthetic,
        )
        cached_bundle = self._version_bundle_cache.get(cache_key)
        if cached_bundle is not None:
            return cached_bundle

        mc_version, _, _ = resolve_recipe_scope(version, profile_id)
        recipes = self.get_version_recipes(
            version,
            profile_id=profile_id,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
        )
        bundle = _build_version_recipe_bundle(recipes, version=mc_version)
        self._version_bundle_cache[cache_key] = bundle
        return bundle

    def clear_mods(self) -> None:
        self._mod_loads.clear()
        self._clear_caches()

    def clear_mods_for_version(self, version: str) -> None:
        legacy_key = version.split("::", 1)[0] if "::" in version else None
        to_remove = [
            jar_path
            for jar_path, load in self._mod_loads.items()
            if load.storage_version == version
            or (legacy_key is not None and load.storage_version == legacy_key)
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

    def _mod_recipes_for_version(self, storage_key: str) -> tuple[Recipe, ...]:
        legacy_key = storage_key.split("::", 1)[0] if "::" in storage_key else None
        recipes: list[Recipe] = []
        for load in self._mod_loads.values():
            if load.storage_version == storage_key or (
                legacy_key is not None and load.storage_version == legacy_key
            ):
                recipes.extend(load.recipes.values())
        return tuple(recipes)

    def get_version_recipes(
        self,
        version: str,
        *,
        profile_id: str | None = None,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> tuple[Recipe, ...]:
        cache_key = self._version_recipe_cache_key(
            version,
            profile_id,
            include_mods,
            include_synthetic,
        )
        cached = self._version_recipe_cache.get(cache_key)
        if cached is not None:
            return cached

        mc_version, resolved_profile, storage_key = resolve_recipe_scope(version, profile_id)
        merged: dict[str, Recipe] = {
            recipe.id: recipe
            for recipe in self._load_vanilla_recipes(mc_version, resolved_profile)
        }

        if include_synthetic:
            for recipe in self._load_synthetic_recipes(mc_version):
                merged[recipe.id] = recipe

        if include_mods:
            for recipe in self._mod_recipes_for_version(storage_key):
                merged[recipe.id] = recipe

        recipes = tuple(merged.values())
        self._version_recipe_cache[cache_key] = recipes
        return recipes

    def lookup(
        self,
        version: str,
        recipe_type: RecipeType | None = None,
        *,
        profile_id: str | None = None,
        include_mods: bool = True,
        include_synthetic: bool = True,
        require_registry: bool = True,
    ) -> RecipeLookup:
        from app.services.mod_service import mod_service

        mc_version, resolved_profile, storage_key = resolve_recipe_scope(version, profile_id)
        if include_mods:
            mod_service.ensure_version_mods_loaded(version, profile_id=profile_id)

        bundle = self.get_recipe_bundle(
            version,
            profile_id=profile_id,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
        )
        registry = (
            get_profile_ingredient_registry(version, profile_id)
            if require_registry
            else None
        )
        if recipe_type is None:
            return RecipeLookup(
                bundle.recipes,
                registry,
                mc_version,
                bundle=bundle,
            )
        filtered = tuple(
            recipe for recipe in bundle.recipes if recipe.recipe_type == recipe_type
        )
        return RecipeLookup(filtered, registry, mc_version, bundle=bundle)

    def get_ingredient_registry(self, version: str) -> IngredientRegistry:
        return get_version_ingredient_registry(version)

    def search_summaries(
        self,
        version: str,
        *,
        profile_id: str | None = None,
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

        needs_registry = bool(
            normalized_focus_item
            or (normalized_uses_item and ":" not in normalized_uses_item)
            or (normalized_produces_item and ":" not in normalized_produces_item)
            or (normalized_query and ":" in normalized_query)
        )
        lookup = self.lookup(
            version,
            profile_id=profile_id,
            include_mods=include_mods,
            include_synthetic=include_synthetic,
            require_registry=needs_registry,
        )

        if normalized_focus_item and focus_role is not None:
            lookup = lookup.focus(
                normalized_focus_item,
                focus_role,
                focus_metadata,
                limit=limit,
            )
        else:
            if normalized_uses_item:
                lookup = lookup.focus(
                    normalized_uses_item,
                    RecipeIngredientRole.INPUT,
                    limit=limit,
                )
            if normalized_produces_item:
                lookup = lookup.focus(
                    normalized_produces_item,
                    RecipeIngredientRole.OUTPUT,
                    limit=limit,
                )

        if normalized_query:
            lookup = lookup.query(normalized_query, limit=limit)

        return lookup.limit(limit).summaries()

    def _load_vanilla_recipes(self, mc_version: str, profile_id: str) -> tuple[Recipe, ...]:
        if self._vanilla_provider is _default_vanilla_provider:
            return _load_vanilla_version_recipes(mc_version, profile_id)
        return tuple(self._vanilla_provider.load(mc_version, profile_id=profile_id).recipes)

    def _load_synthetic_recipes(self, version: str) -> tuple[Recipe, ...]:
        if self._synthetic_provider is _default_synthetic_provider:
            return _load_synthetic_version_recipes(version)
        return tuple(self._synthetic_provider.load(version).recipes)

    def _clear_caches(self) -> None:
        self._version_recipe_cache.clear()
        self._version_bundle_cache.clear()
        _load_vanilla_version_recipes.cache_clear()
        _load_synthetic_version_recipes.cache_clear()
        get_version_ingredient_registry.cache_clear()
        get_profile_ingredient_registry.cache_clear()
        from app.recipes.loaders.item_catalog_loader import _parse_ae2_lang, load_item_catalog

        load_item_catalog.cache_clear()
        _parse_ae2_lang.cache_clear()


recipe_manager = RecipeManager()
