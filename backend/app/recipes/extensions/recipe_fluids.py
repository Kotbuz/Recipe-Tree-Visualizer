from __future__ import annotations

from collections import Counter

from app.recipes.models import RecipeIO


def fluid_io_from_dict(data: dict[str, object]) -> RecipeIO | None:
    amount_raw = data.get("amount", 1000)
    amount = float(amount_raw) if isinstance(amount_raw, (int, float)) else 1000.0

    tag = data.get("tag") or data.get("fluidTag")
    if isinstance(tag, str):
        tag_id = tag if tag.startswith("tag:") else f"tag:{tag}"
        return RecipeIO(item_id=f"fluid:{tag_id}", amount=amount)

    fluid = data.get("fluid")
    if isinstance(fluid, str):
        fluid_id = fluid if fluid.startswith("fluid:") else f"fluid:{fluid}"
        return RecipeIO(item_id=fluid_id, amount=amount)

    return None


def item_io_from_ingredient(ingredient: object) -> RecipeIO | None:
    if isinstance(ingredient, str):
        item_id = ingredient if ":" in ingredient else f"minecraft:{ingredient}"
        return RecipeIO(item_id=item_id, amount=1.0)

    if not isinstance(ingredient, dict):
        return None

    ingredient_type = ingredient.get("type")
    if isinstance(ingredient_type, str) and "fluid" in ingredient_type:
        return fluid_io_from_dict(ingredient)

    if "fluidTag" in ingredient or (
        isinstance(ingredient.get("type"), str) and "fluid" in str(ingredient.get("type"))
    ):
        return fluid_io_from_dict(ingredient)

    tag = ingredient.get("tag")
    if isinstance(tag, str):
        tag_id = tag if tag.startswith("tag:") else f"tag:{tag}"
        return RecipeIO(item_id=tag_id, amount=1.0)

    item = ingredient.get("item") or ingredient.get("id")
    if isinstance(item, str):
        item_id = item if ":" in item else f"minecraft:{item}"
        return RecipeIO(item_id=item_id, amount=1.0)

    return None


def shaped_inputs_from_pattern(
    pattern: object,
    key: object,
) -> list[RecipeIO]:
    if not isinstance(pattern, list) or not isinstance(key, dict):
        return []

    counts: Counter[tuple[str, int | None]] = Counter()
    for row in pattern:
        if not isinstance(row, str):
            continue
        for symbol in row:
            if symbol == " ":
                continue
            ingredient = key.get(symbol)
            if ingredient is None:
                continue
            parsed = item_io_from_ingredient(ingredient)
            if parsed is None:
                continue
            counts[(parsed.item_id, parsed.metadata)] += int(parsed.amount)

    return [
        RecipeIO(item_id=item_id, amount=float(amount), metadata=metadata)
        for (item_id, metadata), amount in counts.items()
    ]


def result_io_from_payload(result: object) -> RecipeIO | None:
    if isinstance(result, str):
        item_id = result if ":" in result else f"minecraft:{result}"
        return RecipeIO(item_id=item_id, amount=1.0)

    if not isinstance(result, dict):
        return None

    item_id = result.get("id") or result.get("item")
    if not isinstance(item_id, str):
        return None

    count = result.get("count", 1)
    if not isinstance(count, (int, float)):
        count = 1

    normalized = item_id if ":" in item_id else f"minecraft:{item_id}"
    return RecipeIO(item_id=normalized, amount=float(count))
