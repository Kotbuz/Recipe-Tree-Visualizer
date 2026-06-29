from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.recipes.adapters import item_id_to_display_name
from app.recipes.ae2_item_match import ae2_items_compatible
from app.recipes.ingredient import IngredientKind
from app.recipes.item_ref import parse_item_needle
from app.recipes.loaders.tag_loader import TagLoader, is_tag_id, normalize_tag_id
from app.recipes.loaders.tag_snapshot_loader import load_tag_snapshot, merge_snapshot_aliases
from app.recipes.models import Recipe
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.services.item_matching import (
    display_name_matches,
    item_id_path_matches,
    items_match,
    quartz_dust_tags_compatible,
)

DEFAULT_ALIASES: dict[str, str] = {
    "planks": "oak planks",
    "logs": "oak log",
    "logs that burn": "oak log",
    "wooden tool materials": "oak planks",
    "stone tool materials": "cobblestone",
    "leathers": "leather",
    "treated wood": "treated wood horizontal",
}


@dataclass(frozen=True)
class Ingredient:
    id: str
    kind: IngredientKind
    display_name: str
    icon_id: str


class IngredientRegistry:
    def __init__(self, tag_loader: TagLoader | None = None) -> None:
        self._tag_loader = tag_loader or TagLoader()
        self._ingredients: dict[str, Ingredient] = {}
        self._tag_members: dict[str, frozenset[str]] = {}
        self._item_tag_index: dict[str, frozenset[str]] | None = None
        self._aliases: dict[str, str] = dict(DEFAULT_ALIASES)

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def load_version(self, version: str) -> None:
        jar_path = VanillaJarProvider().resolve_jar_path(version)
        tag_maps: list[dict[str, frozenset[str]]] = []
        if jar_path is not None:
            tag_maps.append(self._tag_loader.load_from_jar(jar_path))
        snapshot = load_tag_snapshot(version)
        if snapshot:
            tag_maps.append(snapshot)
        if tag_maps:
            self._tag_members = self._tag_loader.merge_tag_maps(*tag_maps)
        self._item_tag_index = None
        merge_snapshot_aliases(self._aliases, version)

    def merge_tags_from_jar(self, jar_path: Path | str) -> None:
        loaded = self._tag_loader.load_from_jar(Path(jar_path))
        if not loaded:
            return
        self._tag_members = self._tag_loader.merge_tag_maps(self._tag_members, loaded)
        self._item_tag_index = None

    def tag_ids_containing_item(self, item_id: str) -> frozenset[str]:
        self._ensure_item_tag_index()
        normalized = self._normalize_item_id(item_id)
        keys = {normalized}
        if ":" in normalized:
            keys.add(normalized.split(":", 1)[1])
        tags: set[str] = set()
        for key in keys:
            tags.update(self._item_tag_index.get(key, ()))
        return frozenset(tags)

    def _ensure_item_tag_index(self) -> None:
        if self._item_tag_index is not None:
            return
        item_tags: dict[str, set[str]] = {}
        for tag_id in self._tag_members:
            for member_id in self.resolve_tag(tag_id):
                if member_id.startswith("tag:"):
                    continue
                member_key = self._normalize_item_id(member_id)
                item_tags.setdefault(member_key, set()).add(normalize_tag_id(tag_id))
                if ":" in member_key:
                    short_key = member_key.split(":", 1)[1]
                    item_tags.setdefault(short_key, set()).add(normalize_tag_id(tag_id))
        self._item_tag_index = {
            key: frozenset(values) for key, values in item_tags.items()
        }

    def register_from_recipes(
        self,
        recipes: tuple[Recipe, ...] | list[Recipe],
        *,
        version: str | None = None,
    ) -> None:
        for recipe in recipes:
            for part in [*recipe.inputs, *recipe.outputs]:
                self.register(part.item_id, metadata=part.metadata, version=version)

    def register(
        self,
        ingredient_id: str,
        *,
        metadata: int | None = None,
        version: str | None = None,
    ) -> Ingredient:
        normalized_id = self._normalize_ingredient_id(ingredient_id)
        registry_key = self._registry_key(normalized_id, metadata)
        existing = self._ingredients.get(registry_key)
        if existing is not None:
            return existing

        if normalized_id.startswith("tag:"):
            display = item_id_to_display_name(normalized_id)
            ingredient = Ingredient(
                id=normalized_id,
                kind=IngredientKind.TAG,
                display_name=display,
                icon_id=self._tag_to_icon_id(normalized_id, display),
            )
        else:
            display = item_id_to_display_name(normalized_id)
            icon_id = self._item_id_to_icon_id(normalized_id)
            use_catalog = version is not None and (
                ":" not in normalized_id or normalized_id.startswith("minecraft:")
            )
            if use_catalog:
                from app.recipes.loaders.item_catalog_loader import (
                    resolve_catalog_display_name,
                    resolve_catalog_icon_id,
                )

                catalog_name = resolve_catalog_display_name(
                    normalized_id,
                    metadata,
                    version=version,
                )
                if catalog_name is not None:
                    display = catalog_name
                catalog_icon = resolve_catalog_icon_id(
                    normalized_id,
                    metadata,
                    version=version,
                )
                if catalog_icon is not None:
                    icon_id = catalog_icon

            ingredient = Ingredient(
                id=normalized_id,
                kind=IngredientKind.ITEM,
                display_name=display,
                icon_id=icon_id,
            )

        self._ingredients[registry_key] = ingredient
        return ingredient

    @staticmethod
    def _registry_key(item_id: str, metadata: int | None) -> str:
        if metadata is None:
            return item_id
        return f"{item_id}#{metadata}"

    def get(self, ingredient_id: str) -> Ingredient | None:
        normalized_id = self._normalize_ingredient_id(ingredient_id)
        return self._ingredients.get(normalized_id)

    def resolve_tag(self, tag_id: str) -> list[str]:
        normalized = normalize_tag_id(tag_id)
        members = self._tag_loader.resolve_transitive(self._tag_members, normalized)
        return sorted(members)

    def list_tag_ids(self) -> list[str]:
        return sorted(self._tag_members.keys())

    def resolve_alias(self, name: str) -> str:
        normalized = name.strip().lower()
        return self._aliases.get(normalized, name)

    def register_alias(self, alias: str, target: str) -> None:
        self._aliases[alias.strip().lower()] = target

    def search(self, query: str, *, limit: int = 20) -> list[Ingredient]:
        needle = query.strip().lower()
        if not needle:
            return []

        results: list[Ingredient] = []
        for ingredient in self._ingredients.values():
            if (
                item_id_path_matches(needle, ingredient.id)
                or display_name_matches(needle, ingredient.display_name)
                or display_name_matches(needle, self.resolve_alias(ingredient.display_name))
            ):
                results.append(ingredient)
                if len(results) >= limit:
                    break
        return results

    def ingredient_matches(
        self,
        needle: str,
        ingredient_id: str,
        *,
        _visiting_tags: frozenset[str] | None = None,
    ) -> bool:
        normalized_needle = needle.strip().lower()
        if not normalized_needle:
            return False

        normalized_id = self._normalize_ingredient_id(ingredient_id)

        if self._matches_ingredient_candidates(normalized_needle, normalized_id):
            return True

        needle_tag_id = self._needle_to_tag_id(normalized_needle)
        if needle_tag_id is not None and self._is_member_of_tag(normalized_id, needle_tag_id):
            return True

        if normalized_id.startswith("tag:"):
            if quartz_dust_tags_compatible(normalized_needle, normalized_id):
                return True

            if ":" in normalized_needle and not is_tag_id(normalized_needle):
                if self._is_member_of_tag(normalized_needle, normalized_id):
                    return True

            visiting = _visiting_tags or frozenset()
            if normalized_id in visiting:
                return False
            visiting = visiting | {normalized_id}
            for member_id in self.resolve_tag(normalized_id):
                if self.ingredient_matches(
                    normalized_needle,
                    member_id,
                    _visiting_tags=visiting,
                ):
                    return True
            return False

        if ":" in normalized_needle:
            if ae2_items_compatible(normalized_id, normalized_needle):
                return True
            for ingredient in self._ingredients.values():
                if ingredient.kind != IngredientKind.ITEM:
                    continue
                if ae2_items_compatible(normalized_id, ingredient.id) and (
                    items_match(normalized_needle, ingredient.display_name.lower())
                    or self._item_ids_equivalent(normalized_needle, ingredient.id)
                ):
                    return True

        return False

    def _matches_ingredient_candidates(self, needle: str, ingredient_id: str) -> bool:
        needle_base, _ = parse_item_needle(needle, None)
        display_name = item_id_to_display_name(ingredient_id)
        alias = self.resolve_alias(display_name).lower()
        candidates = {
            ingredient_id.lower(),
            display_name.lower(),
            alias,
        }

        registered = self._ingredients.get(ingredient_id)
        if registered is not None:
            candidates.add(registered.display_name.lower())
        else:
            prefix = f"{ingredient_id}#"
            for key, ingredient in self._ingredients.items():
                if key.startswith(prefix):
                    candidates.add(ingredient.display_name.lower())

        return any(
            items_match(needle_base, candidate) or self._item_ids_equivalent(needle_base, candidate)
            for candidate in candidates
        )

    def _needle_to_tag_id(self, needle: str) -> str | None:
        if is_tag_id(needle):
            return normalize_tag_id(needle)

        for ingredient in self._ingredients.values():
            if ingredient.kind != IngredientKind.TAG:
                continue
            if needle == ingredient.display_name.lower():
                return normalize_tag_id(ingredient.id)

        return None

    def _is_member_of_tag(self, item_id: str, tag_id: str) -> bool:
        normalized_tag = normalize_tag_id(tag_id)
        return normalized_tag in self.tag_ids_containing_item(item_id)

    @staticmethod
    def _item_ids_equivalent(left: str, right: str) -> bool:
        if left == right:
            return True
        return left.split(":", 1)[-1] == right.split(":", 1)[-1]

    @staticmethod
    def _normalize_item_id(item_id: str) -> str:
        return item_id.strip().lower()

    @staticmethod
    def _normalize_ingredient_id(ingredient_id: str) -> str:
        if ingredient_id.startswith("tag:"):
            return ingredient_id
        return ingredient_id

    @staticmethod
    def _item_id_to_icon_id(item_id: str) -> str:
        if ":" in item_id:
            namespace, path = item_id.split(":", 1)
            normalized_path = path.replace(" ", "_").lower()
            if namespace != "minecraft":
                return f"{namespace}_{normalized_path}"
            return normalized_path
        return item_id.replace(" ", "_").lower()

    @staticmethod
    def _display_name_to_icon_id(display_name: str) -> str:
        return display_name.strip().lower().replace(" ", "_")

    def _tag_to_icon_id(self, tag_id: str, display_name: str) -> str:
        alias_target = self.resolve_alias(display_name)
        if alias_target != display_name:
            return self._display_name_to_icon_id(alias_target)

        members = self.resolve_tag(tag_id)
        if members:
            return self._item_id_to_icon_id(self._pick_representative_member(tag_id, members))

        return self._display_name_to_icon_id(display_name)

    @staticmethod
    def _pick_representative_member(tag_id: str, members: list[str]) -> str:
        path = tag_id.removeprefix("tag:c:")
        material = path.split("/", 1)[-1].lower() if "/" in path else ""
        material_variants = [material]
        if material.endswith("s") and len(material) > 1:
            material_variants.append(material[:-1])

        for variant in material_variants:
            if not variant:
                continue
            for member in sorted(members):
                member_path = member.split(":", 1)[-1].lower()
                if variant in member_path:
                    return member

        return sorted(members)[0]


_default_tag_loader = TagLoader()


@lru_cache(maxsize=32)
def get_profile_ingredient_registry(
    version: str,
    profile_id: str | None = None,
) -> IngredientRegistry:
    from app.recipes.manager import recipe_manager, resolve_recipe_scope

    mc_version, resolved_profile, storage_key = resolve_recipe_scope(version, profile_id)
    registry = IngredientRegistry(_default_tag_loader)
    registry.load_version(mc_version)
    for jar_path in recipe_manager.mod_jar_paths_for_storage(storage_key):
        registry.merge_tags_from_jar(jar_path)
    registry.register_from_recipes(
        recipe_manager.get_version_recipes(
            mc_version,
            profile_id=resolved_profile,
            include_mods=True,
        ),
        version=mc_version,
    )
    return registry


@lru_cache(maxsize=8)
def get_version_ingredient_registry(version: str) -> IngredientRegistry:
    from app.services.profile_storage import DEFAULT_PROFILE_ID

    return get_profile_ingredient_registry(version, DEFAULT_PROFILE_ID)
