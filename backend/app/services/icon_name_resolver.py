from __future__ import annotations

from app.recipes.registry import DEFAULT_ALIASES, get_version_ingredient_registry


def resolve_icon_item_name(item_name: str, version: str | None = None) -> str:
    normalized = item_name.strip().lower()
    if version is not None:
        return get_version_ingredient_registry(version).resolve_alias(item_name)
    return DEFAULT_ALIASES.get(normalized, item_name)
