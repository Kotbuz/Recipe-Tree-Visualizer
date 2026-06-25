from __future__ import annotations

# Теги и обобщённые названия из рецептов → конкретный предмет для иконки.
_ICON_ALIASES: dict[str, str] = {
    "planks": "oak planks",
    "logs": "oak logs",
    "logs that burn": "oak logs",
    "wooden tool materials": "oak planks",
    "stone tool materials": "cobblestone",
}


def resolve_icon_item_name(item_name: str) -> str:
    normalized = item_name.strip().lower()
    return _ICON_ALIASES.get(normalized, item_name)
