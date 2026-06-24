from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.recipe_file import RecipeSummary

ROOT_DIR = Path(__file__).resolve().parents[2]
MINECRAFT_VERSIONS_DIR = ROOT_DIR.parent / "Minecraft versions"


def _pretty_item_name(item_id: str | None) -> str:
    if not item_id:
        return "unknown"
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


def _collect_inputs(recipe_data: dict[str, Any]) -> list[str]:
    inputs: list[str] = []
    unique: set[str] = set()

    def add(item_id: str | None) -> None:
        name = _pretty_item_name(
            _extract_item_id(item_id) if isinstance(item_id, (str, dict)) else None
        )
        if name and name not in unique:
            unique.add(name)
            inputs.append(name)

    if "ingredients" in recipe_data and isinstance(recipe_data["ingredients"], list):
        for ingredient in recipe_data["ingredients"]:
            if isinstance(ingredient, list):
                for item in ingredient:
                    add(_extract_item_id(item))
            else:
                add(_extract_item_id(ingredient))

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
                add(_extract_item_id(key_value))

    if "ingredient" in recipe_data:
        ingredient = recipe_data["ingredient"]
        if isinstance(ingredient, list):
            for item in ingredient:
                add(_extract_item_id(item))
        else:
            add(_extract_item_id(ingredient))

    if not inputs and "key" in recipe_data and isinstance(recipe_data["key"], dict):
        for value in recipe_data["key"].values():
            add(_extract_item_id(value))

    return inputs


def _collect_outputs(recipe_data: dict[str, Any]) -> list[str]:
    outputs: list[str] = []
    unique: set[str] = set()

    def add(item_id: str | None) -> None:
        name = _pretty_item_name(item_id)
        if name and name not in unique:
            unique.add(name)
            outputs.append(name)

    if "result" in recipe_data:
        result = recipe_data["result"]
        if isinstance(result, dict):
            add(_extract_item_id(result))
        else:
            add(_extract_item_id(result))

    if "results" in recipe_data and isinstance(recipe_data["results"], list):
        for result in recipe_data["results"]:
            if isinstance(result, dict):
                add(_extract_item_id(result))
            else:
                add(_extract_item_id(result))

    if "output" in recipe_data:
        add(_extract_item_id(recipe_data["output"]))

    return outputs


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


class RecipeService:
    def list_recipes(self, version: str = "26.2") -> list[RecipeSummary]:
        recipe_dir = MINECRAFT_VERSIONS_DIR / version / "recipe"
        if not recipe_dir.exists() or not recipe_dir.is_dir():
            return []

        recipes: list[RecipeSummary] = []
        for json_file in sorted(recipe_dir.glob("*.json")):
            recipe = _load_recipe_file(json_file)
            if recipe is not None:
                recipes.append(recipe)
        return recipes


recipe_service = RecipeService()
