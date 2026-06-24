from collections import Counter

from app.parser.exceptions import JarParseError
from app.parser.models import RawRecipeFile
from app.parser.recipe_types import (
    BLASTING,
    CAMPFIRE_COOKING,
    CRAFTING_SHAPED,
    CRAFTING_SHAPELESS,
    MACHINE_BY_TYPE,
    SMELTING,
    SMOKING,
    STONECUTTING,
    is_supported_recipe_type,
    normalize_recipe_type,
)
from app.schemas.domain import Recipe, RecipeIO


class RecipeExtractor:
    def can_extract(self, recipe_file: RawRecipeFile) -> bool:
        recipe_type = recipe_file.data.get("type")
        return isinstance(recipe_type, str) and is_supported_recipe_type(recipe_type)

    def extract(self, recipe_file: RawRecipeFile, mod_id: str) -> Recipe:
        data = recipe_file.data
        raw_type = data.get("type")
        if not isinstance(raw_type, str):
            raise JarParseError(f"Recipe {recipe_file.recipe_id} is missing type")

        recipe_type = normalize_recipe_type(raw_type)
        machine_id = MACHINE_BY_TYPE.get(recipe_type)
        if machine_id is None:
            raise JarParseError(f"Unsupported recipe type: {raw_type}")

        inputs = self._extract_inputs(recipe_type, data)
        outputs = [self._extract_result(data)]

        duration_ticks: int | None = None
        cooking_time = data.get("cookingtime") or data.get("cookingTime")
        if isinstance(cooking_time, int):
            duration_ticks = cooking_time

        return Recipe(
            id=recipe_file.recipe_id,
            machine_id=machine_id,
            inputs=inputs,
            outputs=outputs,
            duration_ticks=duration_ticks,
            mod_id=mod_id,
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

        counts: Counter[str] = Counter()
        for row in pattern:
            if not isinstance(row, str):
                raise JarParseError("Shaped recipe pattern rows must be strings")
            for symbol in row:
                if symbol == " ":
                    continue
                ingredient = key.get(symbol)
                if ingredient is None:
                    raise JarParseError(f"Missing ingredient for symbol '{symbol}'")
                item_id = self._parse_ingredient_id(ingredient)
                counts[item_id] += 1

        return [
            RecipeIO(item_id=item_id, amount=float(amount)) for item_id, amount in counts.items()
        ]

    def _extract_shapeless_inputs(self, data: dict[str, object]) -> list[RecipeIO]:
        ingredients = data.get("ingredients")
        if not isinstance(ingredients, list):
            raise JarParseError("Shapeless recipe requires ingredients list")

        counts: Counter[str] = Counter()
        for ingredient in ingredients:
            item_id = self._parse_ingredient_id(ingredient)
            counts[item_id] += 1

        return [
            RecipeIO(item_id=item_id, amount=float(amount)) for item_id, amount in counts.items()
        ]

    def _extract_single_input(self, data: dict[str, object], key: str) -> list[RecipeIO]:
        ingredient = data.get(key)
        if ingredient is None:
            raise JarParseError(f"Recipe is missing {key}")
        item_id = self._parse_ingredient_id(ingredient)
        return [RecipeIO(item_id=item_id, amount=1.0)]

    def _extract_result(self, data: dict[str, object]) -> RecipeIO:
        result = data.get("result")
        if result is None:
            raise JarParseError("Recipe is missing result")

        if isinstance(result, str):
            return RecipeIO(item_id=self._normalize_item_id(result), amount=1.0)

        if isinstance(result, dict):
            item_id = result.get("id") or result.get("item")
            if not isinstance(item_id, str):
                raise JarParseError("Recipe result must include id or item")
            count = result.get("count", 1)
            if not isinstance(count, int | float):
                count = 1
            return RecipeIO(item_id=self._normalize_item_id(item_id), amount=float(count))

        raise JarParseError("Unsupported recipe result format")

    def _parse_ingredient_id(self, ingredient: object) -> str:
        if isinstance(ingredient, str):
            return self._normalize_item_id(ingredient)

        if isinstance(ingredient, dict):
            if "tag" in ingredient:
                tag = ingredient["tag"]
                if isinstance(tag, str):
                    return self._normalize_item_id(tag)
            item = ingredient.get("item") or ingredient.get("id")
            if isinstance(item, str):
                return self._normalize_item_id(item)

        if isinstance(ingredient, list):
            for option in ingredient:
                return self._parse_ingredient_id(option)

        raise JarParseError(f"Unsupported ingredient format: {ingredient!r}")

    def _normalize_item_id(self, raw: str) -> str:
        if raw.startswith("#"):
            return f"tag:{raw.removeprefix('#')}"
        return raw
