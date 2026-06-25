from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.schemas.recipe_file import RecipeItem, RecipeSummary
from app.services.item_matching import items_match


def _pretty_item_name(item_id: str | None) -> str:
    if not item_id:
        return "unknown"
    if item_id.startswith("#"):
        item_id = item_id[1:]
    if ":" in item_id:
        item_id = item_id.split(":", 1)[1]
    return item_id.replace("_", " ")


def _map_machine_type(recipe_type: str) -> str:
    mapping = {
        "minecraft:crafting_shaped": "Верстак",
        "minecraft:crafting_shapeless": "Верстак",
        "minecraft:smelting": "Печь",
        "minecraft:smoking": "Печь",
        "minecraft:blasting": "Печь",
        "minecraft:campfire_cooking": "Печь",
        "minecraft:smithing": "Наковальня",
        "minecraft:smithing_transform": "Наковальня",
        "minecraft:stonecutting": "Наковальня",
        "minecraft:smithing": "Наковальня",
    }
    if recipe_type in mapping:
        return mapping[recipe_type]
    if ":" in recipe_type:
        raw = recipe_type.split(":", 1)[1]
    else:
        raw = recipe_type
    return raw.replace("_", " ").capitalize()


def _extract_item_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "item" in value:
            return value["item"]
        if "id" in value:
            return value["id"]
        if "result" in value and isinstance(value["result"], str):
            return value["result"]
        if "ingredient" in value and isinstance(value["ingredient"], str):
            return value["ingredient"]
    return None


def _extract_item_amount(value: Any) -> int:
    if value is None:
        return 1
    if isinstance(value, dict):
        if "count" in value:
            return int(value["count"])
        if "amount" in value:
            return int(value["amount"])
    return 1


def _collect_inputs(recipe_data: dict[str, Any]) -> list[RecipeItem]:
    inputs_dict: dict[str, int] = {}

    def add(item_id: str | None, amount: int = 1) -> None:
        name = _pretty_item_name(
            _extract_item_id(item_id) if isinstance(item_id, (str, dict)) else None
        )
        if name:
            inputs_dict[name] = inputs_dict.get(name, 0) + amount

    if "ingredients" in recipe_data and isinstance(recipe_data["ingredients"], list):
        for ingredient in recipe_data["ingredients"]:
            if isinstance(ingredient, list):
                for item in ingredient:
                    add(_extract_item_id(item), _extract_item_amount(item))
            else:
                add(_extract_item_id(ingredient), _extract_item_amount(ingredient))

    if (
        "pattern" in recipe_data
        and isinstance(recipe_data["pattern"], list)
        and isinstance(recipe_data.get("key"), dict)
    ):
        for row in recipe_data["pattern"]:
            if not isinstance(row, str):
                continue
            for symbol in row:
                if symbol == " ":
                    continue
                key_value = recipe_data["key"].get(symbol)
                add(_extract_item_id(key_value), _extract_item_amount(key_value))

    if "ingredient" in recipe_data:
        ingredient = recipe_data["ingredient"]
        if isinstance(ingredient, list):
            for item in ingredient:
                add(_extract_item_id(item), _extract_item_amount(item))
        else:
            add(_extract_item_id(ingredient), _extract_item_amount(ingredient))

    if not inputs_dict and "key" in recipe_data and isinstance(recipe_data["key"], dict):
        for value in recipe_data["key"].values():
            add(_extract_item_id(value), _extract_item_amount(value))

    return [RecipeItem(name=name, amount=amount) for name, amount in inputs_dict.items()]


def _collect_outputs(recipe_data: dict[str, Any]) -> list[RecipeItem]:
    outputs_dict: dict[str, int] = {}

    def add(item_id: str | None, amount: int = 1) -> None:
        name = _pretty_item_name(item_id)
        if name:
            outputs_dict[name] = outputs_dict.get(name, 0) + amount

    if "result" in recipe_data:
        result = recipe_data["result"]
        if isinstance(result, dict):
            add(_extract_item_id(result), _extract_item_amount(result))
        else:
            add(_extract_item_id(result), _extract_item_amount(result))

    if "results" in recipe_data and isinstance(recipe_data["results"], list):
        for result in recipe_data["results"]:
            if isinstance(result, dict):
                add(_extract_item_id(result), _extract_item_amount(result))
            else:
                add(_extract_item_id(result), _extract_item_amount(result))

    if "output" in recipe_data:
        add(_extract_item_id(recipe_data["output"]), _extract_item_amount(recipe_data["output"]))

    return [RecipeItem(name=name, amount=amount) for name, amount in outputs_dict.items()]


def _load_recipe_file(file_path: Path) -> RecipeSummary | None:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    recipe_type = data.get("type", "unknown")
    inputs = _collect_inputs(data)
    outputs = _collect_outputs(data)

    if not outputs:
        return None

    return RecipeSummary(
        recipe_id=file_path.stem,
        machine_type=recipe_type,
        machine_name=_map_machine_type(recipe_type),
        inputs=inputs,
        outputs=outputs,
    )


def _load_recipes_for_version(version: str) -> tuple[RecipeSummary, ...]:
    recipe_dir = get_settings().minecraft_versions_path / version / "recipe"
    if not recipe_dir.exists() or not recipe_dir.is_dir():
        return ()

    recipes: list[RecipeSummary] = []
    for json_file in sorted(recipe_dir.glob("*.json")):
        recipe = _load_recipe_file(json_file)
        if recipe is not None:
            recipes.append(recipe)
    return tuple(recipes)


class RecipeService:
    def search_recipes(
        self,
        version: str = "26.2",
        query: str | None = None,
        uses_item: str | None = None,
        produces_item: str | None = None,
        limit: int = 50,
    ) -> list[RecipeSummary]:
        recipes = self._get_recipes(version)
        normalized_query = query.strip().lower() if query else ""
        normalized_uses_item = uses_item.strip() if uses_item else ""
        normalized_produces_item = produces_item.strip() if produces_item else ""

        if not normalized_query and not normalized_uses_item and not normalized_produces_item:
            return []

        results: list[RecipeSummary] = []
        for recipe in recipes:
            if normalized_uses_item and not any(
                items_match(normalized_uses_item, item.name) for item in recipe.inputs
            ):
                continue

            if normalized_produces_item and not any(
                items_match(normalized_produces_item, item.name) for item in recipe.outputs
            ):
                continue

            if normalized_query and not any(
                normalized_query in item.name.lower() for item in recipe.outputs
            ):
                continue

            results.append(recipe)
            if len(results) >= limit:
                break

        return results

    @staticmethod
    @lru_cache(maxsize=8)
    def _get_recipes(version: str) -> tuple[RecipeSummary, ...]:
        return _load_recipes_for_version(version)

    def get_recipes(self, version: str) -> tuple[RecipeSummary, ...]:
        return self._get_recipes(version)


recipe_service = RecipeService()
