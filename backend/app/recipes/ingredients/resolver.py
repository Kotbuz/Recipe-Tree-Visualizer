from __future__ import annotations

from dataclasses import dataclass

from app.parser.exceptions import JarParseError
from app.recipes.loaders.ore_dict_loader import OreDictEntry, load_ore_dict
from app.recipes.loaders.tag_loader import TagLoader, normalize_tag_id

_FORGE_ITEM_CONSTANTS: dict[str, str] = {
    "EMERALD": "minecraft:emerald",
    "ENDER_PEARL": "minecraft:ender_pearl",
    "PURPLE_DYE": "minecraft:dye",
    "DYE": "minecraft:dye",
    "WOOL": "minecraft:wool",
    "PLANKS": "minecraft:planks",
    "LOG": "minecraft:log",
    "STONE": "minecraft:stone",
    "COBBLESTONE": "minecraft:cobblestone",
    "IRON_INGOT": "minecraft:iron_ingot",
    "GOLD_INGOT": "minecraft:gold_ingot",
    "DIAMOND": "minecraft:diamond",
    "REDSTONE": "minecraft:redstone",
    "STICK": "minecraft:stick",
    "STRING": "minecraft:string",
    "GLASS": "minecraft:glass",
    "CHEST": "minecraft:chest",
    "COMPARATOR": "minecraft:comparator",
}

_FORGE_CONSTANT_METADATA: dict[str, int] = {
    "PURPLE_DYE": 5,
}


@dataclass(frozen=True)
class ParsedIngredient:
    item_id: str
    metadata: int | None = None


class IngredientResolver:
    def __init__(
        self,
        *,
        version: str,
        ore_dict: dict[str, OreDictEntry] | None = None,
        tag_members: dict[str, frozenset[str]] | None = None,
        tag_loader: TagLoader | None = None,
    ) -> None:
        self._version = version
        self._ore_dict = ore_dict if ore_dict is not None else load_ore_dict(version)
        self._tag_members = tag_members or {}
        self._tag_loader = tag_loader or TagLoader()

    def resolve(self, ingredient: object) -> ParsedIngredient:
        if isinstance(ingredient, list):
            if not ingredient:
                raise JarParseError("Ingredient alternative list is empty")
            return self.resolve(ingredient[0])

        if isinstance(ingredient, str):
            return self._resolve_item_ref(ingredient)

        if isinstance(ingredient, dict):
            ingredient_type = ingredient.get("type")
            if ingredient_type == "forge:ore_dict":
                ore_name = ingredient.get("ore")
                if isinstance(ore_name, str):
                    return self._resolve_ore_dict(ore_name)

            if "tag" in ingredient:
                tag = ingredient["tag"]
                if isinstance(tag, str):
                    return self._resolve_tag(tag)

            item = ingredient.get("item") or ingredient.get("id")
            if isinstance(item, str):
                metadata = ingredient.get("metadata", ingredient.get("data"))
                if metadata is not None and not isinstance(metadata, int):
                    metadata = None
                return self._resolve_item_ref(item, metadata=metadata)

        raise JarParseError(f"Unsupported ingredient format: {ingredient!r}")

    def _resolve_ore_dict(self, ore_name: str) -> ParsedIngredient:
        entry = self._ore_dict.get(ore_name)
        if entry is None:
            raise JarParseError(f"Unknown ore dictionary entry: {ore_name}")
        return ParsedIngredient(item_id=entry.item_id, metadata=entry.metadata)

    def _resolve_tag(self, tag: str) -> ParsedIngredient:
        normalized = normalize_tag_id(tag)
        members = self._tag_loader.resolve_transitive(self._tag_members, normalized)
        if not members:
            return ParsedIngredient(item_id=normalized)
        first = sorted(members)[0]
        return ParsedIngredient(item_id=first)

    def _resolve_item_ref(self, raw: str, metadata: int | None = None) -> ParsedIngredient:
        if raw.startswith("#"):
            constant = raw.removeprefix("#")
            mapped = _FORGE_ITEM_CONSTANTS.get(constant)
            if mapped is not None:
                return ParsedIngredient(
                    item_id=mapped,
                    metadata=_FORGE_CONSTANT_METADATA.get(constant, metadata),
                )
            return self._resolve_ore_dict(constant)

        if raw.startswith("tag:") or (":" not in raw and raw.startswith("#")):
            return self._resolve_tag(raw)

        if ":" not in raw:
            return ParsedIngredient(item_id=f"minecraft:{raw}", metadata=metadata)

        return ParsedIngredient(item_id=raw, metadata=metadata)


def create_ingredient_resolver(
    version: str,
    *,
    tag_members: dict[str, frozenset[str]] | None = None,
) -> IngredientResolver:
    return IngredientResolver(version=version, tag_members=tag_members)
