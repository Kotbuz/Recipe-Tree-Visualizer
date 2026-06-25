from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.recipes.adapters import item_id_to_display_name
from app.recipes.ingredient import IngredientKind
from app.recipes.loaders.tag_loader import TagLoader, is_tag_id, normalize_tag_id
from app.recipes.models import Recipe
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.services.item_matching import items_match

DEFAULT_ALIASES: dict[str, str] = {
    "planks": "oak planks",
    "logs": "oak log",
    "logs that burn": "oak log",
    "wooden tool materials": "oak planks",
    "stone tool materials": "cobblestone",
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
        self._aliases: dict[str, str] = dict(DEFAULT_ALIASES)

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def load_version(self, version: str) -> None:
        jar_path = VanillaJarProvider().resolve_jar_path(version)
        if jar_path is None:
            return
        self._tag_members = self._tag_loader.load_from_jar(jar_path)

    def merge_tags_from_jar(self, jar_path: Path | str) -> None:
        loaded = self._tag_loader.load_from_jar(Path(jar_path))
        if not loaded:
            return
        self._tag_members = self._tag_loader.merge_tag_maps(self._tag_members, loaded)

    def register_from_recipes(self, recipes: tuple[Recipe, ...] | list[Recipe]) -> None:
        for recipe in recipes:
            for part in [*recipe.inputs, *recipe.outputs]:
                self.register(part.item_id)

    def register(self, ingredient_id: str) -> Ingredient:
        normalized_id = self._normalize_ingredient_id(ingredient_id)
        existing = self._ingredients.get(normalized_id)
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
            ingredient = Ingredient(
                id=normalized_id,
                kind=IngredientKind.ITEM,
                display_name=item_id_to_display_name(normalized_id),
                icon_id=self._item_id_to_icon_id(normalized_id),
            )

        self._ingredients[normalized_id] = ingredient
        return ingredient

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
                needle in ingredient.id.lower()
                or needle in ingredient.display_name.lower()
                or needle in self.resolve_alias(ingredient.display_name).lower()
            ):
                results.append(ingredient)
                if len(results) >= limit:
                    break
        return results

    def ingredient_matches(self, needle: str, ingredient_id: str) -> bool:
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
            for member_id in self.resolve_tag(normalized_id):
                if self.ingredient_matches(normalized_needle, member_id):
                    return True

        return False

    def _matches_ingredient_candidates(self, needle: str, ingredient_id: str) -> bool:
        display_name = item_id_to_display_name(ingredient_id)
        alias = self.resolve_alias(display_name).lower()
        candidates = {
            ingredient_id.lower(),
            display_name.lower(),
            alias,
        }
        return any(
            items_match(needle, candidate) or self._item_ids_equivalent(needle, candidate)
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
        members = self.resolve_tag(tag_id)
        if not members:
            return False

        normalized_item = self._normalize_item_id(item_id)
        for member in members:
            if self._item_ids_equivalent(normalized_item, self._normalize_item_id(member)):
                return True
        return False

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
        raw = item_id.split(":", maxsplit=1)[-1]
        return raw.replace(" ", "_").lower()

    @staticmethod
    def _display_name_to_icon_id(display_name: str) -> str:
        return display_name.strip().lower().replace(" ", "_")

    def _tag_to_icon_id(self, tag_id: str, display_name: str) -> str:
        alias_target = self.resolve_alias(display_name)
        if alias_target != display_name:
            return self._display_name_to_icon_id(alias_target)

        members = self.resolve_tag(tag_id)
        if members:
            return self._item_id_to_icon_id(members[0])

        return self._display_name_to_icon_id(display_name)


_default_tag_loader = TagLoader()


@lru_cache(maxsize=8)
def get_version_ingredient_registry(version: str) -> IngredientRegistry:
    from app.recipes.manager import recipe_manager

    registry = IngredientRegistry(_default_tag_loader)
    registry.load_version(version)
    for jar_path in recipe_manager.mod_jar_paths_for_version(version):
        registry.merge_tags_from_jar(jar_path)
    registry.register_from_recipes(recipe_manager.get_version_recipes(version))
    return registry
