from collections import Counter

from app.parser.exceptions import JarParseError
from app.parser.recipe_types import (
    BLASTING,
    CAMPFIRE_COOKING,
    CRAFTING_SHAPED,
    CRAFTING_SHAPELESS,
    SMELTING,
    SMOKING,
    STONECUTTING,
    is_supported_recipe_type,
    normalize_recipe_type,
)
from app.recipes.category import category_for_canonical_type
from app.recipes.extensions import CategoryExtensionRegistry, default_category_extensions
from app.recipes.ingredients.resolver import IngredientResolver, ParsedIngredient
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType


class JsonRecipeParser:
    def __init__(
        self,
        extensions: CategoryExtensionRegistry | None = None,
        resolver: IngredientResolver | None = None,
    ) -> None:
        self._extensions = extensions or default_category_extensions()
        self._resolver = resolver

    def can_parse(self, data: dict[str, object]) -> bool:
        recipe_type = data.get("type")
        if not isinstance(recipe_type, str):
            return False
        if is_supported_recipe_type(recipe_type):
            return True
        return self._extensions.matches(recipe_type)

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None = None,
    ) -> Recipe | None:
        raw_type = data.get("type")
        if not isinstance(raw_type, str):
            return None

        if is_supported_recipe_type(raw_type):
            canonical_type = normalize_recipe_type(raw_type)
            return self._parse_recipe(
                recipe_id,
                data,
                canonical_type=canonical_type,
                raw_type=raw_type,
                source=source,
                mod_id=mod_id,
            )

        extension = self._extensions.find(raw_type)
        if extension is None:
            return None

        from app.recipes.extensions.forge import ForgeRecipeExtension

        if isinstance(extension, ForgeRecipeExtension):
            canonical_type = ForgeRecipeExtension.canonical_type_for(raw_type)
            if canonical_type is None:
                return None
            return self._parse_recipe(
                recipe_id,
                data,
                canonical_type=canonical_type,
                raw_type=raw_type,
                source=source,
                mod_id=mod_id,
            )

        return extension.parse(recipe_id, data, source=source, mod_id=mod_id)

    def skip_reason(self, data: dict[str, object]) -> str | None:
        raw_type = data.get("type")
        if not isinstance(raw_type, str):
            return None
        extension = self._extensions.find(raw_type)
        if extension is None:
            return None
        return extension.skip_reason(data)

    def _parse_recipe(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        canonical_type: str,
        raw_type: str,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        category = category_for_canonical_type(canonical_type)

        try:
            inputs = self._extract_inputs(canonical_type, data)
            outputs = [self._extract_result(data)]
        except JarParseError:
            return None

        duration_ticks: int | None = None
        cooking_time = data.get("cookingtime") or data.get("cookingTime")
        if isinstance(cooking_time, int):
            duration_ticks = cooking_time

        return Recipe(
            id=recipe_id,
            recipe_type=RecipeType(canonical_type),
            category_id=category.id,
            catalyst_id=category.catalyst_id,
            inputs=inputs,
            outputs=outputs,
            duration_ticks=duration_ticks,
            source=source,
            mod_id=mod_id,
            raw_type=raw_type,
        )

    def _extract_inputs(self, recipe_type: str, data: dict[str, object]) -> list[RecipeIO]:
        if recipe_type == CRAFTING_SHAPED:
            return self._extract_shaped_inputs(data)
        if recipe_type == CRAFTING_SHAPELESS:
            return self._extract_shapeless_inputs(data)
        if recipe_type in {SMELTING, BLASTING, SMOKING, CAMPFIRE_COOKING}:
            return self._extract_single_input(data, key="ingredient")
        if recipe_type == STONECUTTING:
            return self._extract_single_input(data, key="ingredient")
        raise JarParseError(f"Unsupported recipe type: {recipe_type}")

    def _extract_shaped_inputs(self, data: dict[str, object]) -> list[RecipeIO]:
        pattern = data.get("pattern")
        key = data.get("key")
        if not isinstance(pattern, list) or not isinstance(key, dict):
            raise JarParseError("Shaped recipe requires pattern and key")

        counts: Counter[tuple[str, int | None]] = Counter()
        for row in pattern:
            if not isinstance(row, str):
                raise JarParseError("Shaped recipe pattern rows must be strings")
            for symbol in row:
                if symbol == " ":
                    continue
                ingredient = key.get(symbol)
                if ingredient is None:
                    raise JarParseError(f"Missing ingredient for symbol '{symbol}'")
                parsed = self._resolve_ingredient(ingredient)
                if parsed.item_id == "minecraft:air":
                    continue
                counts[(parsed.item_id, parsed.metadata)] += 1

        return [
            RecipeIO(item_id=item_id, amount=float(amount), metadata=metadata)
            for (item_id, metadata), amount in counts.items()
        ]

    def _extract_shapeless_inputs(self, data: dict[str, object]) -> list[RecipeIO]:
        ingredients = data.get("ingredients")
        if not isinstance(ingredients, list):
            raise JarParseError("Shapeless recipe requires ingredients list")

        counts: Counter[tuple[str, int | None]] = Counter()
        for ingredient in ingredients:
            parsed = self._resolve_ingredient(ingredient)
            if parsed.item_id == "minecraft:air":
                continue
            counts[(parsed.item_id, parsed.metadata)] += 1

        return [
            RecipeIO(item_id=item_id, amount=float(amount), metadata=metadata)
            for (item_id, metadata), amount in counts.items()
        ]

    def _extract_single_input(self, data: dict[str, object], key: str) -> list[RecipeIO]:
        ingredient = data.get(key)
        if ingredient is None:
            raise JarParseError(f"Recipe is missing {key}")
        parsed = self._resolve_ingredient(ingredient)
        return [
            RecipeIO(item_id=parsed.item_id, amount=1.0, metadata=parsed.metadata),
        ]

    def _extract_result(self, data: dict[str, object]) -> RecipeIO:
        result = data.get("result")
        if result is None:
            raise JarParseError("Recipe is missing result")

        if isinstance(result, str):
            parsed = self._resolve_ingredient(result)
            return RecipeIO(item_id=parsed.item_id, amount=1.0, metadata=parsed.metadata)

        if isinstance(result, dict):
            item_id = result.get("id") or result.get("item")
            if not isinstance(item_id, str):
                raise JarParseError("Recipe result must include id or item")
            count = result.get("count", 1)
            if not isinstance(count, int | float):
                count = 1
            metadata = result.get("metadata", result.get("data"))
            if metadata is not None and not isinstance(metadata, int):
                metadata = None
            parsed = self._resolve_ingredient(
                {"item": item_id, "metadata": metadata} if metadata is not None else item_id
            )
            return RecipeIO(
                item_id=parsed.item_id,
                amount=float(count),
                metadata=parsed.metadata if parsed.metadata is not None else metadata,
            )

        raise JarParseError("Unsupported recipe result format")

    def _resolve_ingredient(self, ingredient: object) -> ParsedIngredient:
        if self._resolver is not None:
            return self._resolver.resolve(ingredient)

        item_id = self._parse_ingredient_id_legacy(ingredient)
        return ParsedIngredient(item_id=item_id)

    def _parse_ingredient_id_legacy(self, ingredient: object) -> str:
        if isinstance(ingredient, str):
            return self._normalize_item_id(ingredient)

        if isinstance(ingredient, dict):
            if "tag" in ingredient:
                tag = ingredient["tag"]
                if isinstance(tag, str):
                    return self._as_tag_id(tag)
            item = ingredient.get("item") or ingredient.get("id")
            if isinstance(item, str):
                return self._normalize_item_id(item)

        if isinstance(ingredient, list):
            for option in ingredient:
                return self._parse_ingredient_id_legacy(option)

        raise JarParseError(f"Unsupported ingredient format: {ingredient!r}")

    def _normalize_item_id(self, raw: str) -> str:
        if raw.startswith("#"):
            return self._as_tag_id(raw.removeprefix("#"))
        return raw

    def _as_tag_id(self, raw: str) -> str:
        normalized = raw.removeprefix("#")
        if normalized.startswith("tag:"):
            return normalized
        return f"tag:{normalized}"
