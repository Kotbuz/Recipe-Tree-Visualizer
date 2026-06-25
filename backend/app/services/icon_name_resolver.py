from __future__ import annotations

from app.recipes.registry import DEFAULT_ALIASES


def resolve_icon_item_name(item_name: str) -> str:
    normalized = item_name.strip().lower()
    return DEFAULT_ALIASES.get(normalized, item_name)
