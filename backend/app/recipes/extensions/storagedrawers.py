from __future__ import annotations

from app.parser.recipe_types import normalize_recipe_type
from app.recipes.extensions.base import CategoryExtension
from app.recipes.models import Recipe

_STORAGE_DRAWERS_PREFIX = "storagedrawers:"
_DISPLAY_NAMES: dict[str, str] = {
    "storagedrawers:add_upgrade": "Storage Drawers upgrade",
    "storagedrawers:add_detached_upgrade": "Storage Drawers detached upgrade",
    "storagedrawers:keyring": "Storage Drawers keyring",
    "storagedrawers:personal_key_cycle": "Storage Drawers personal key",
    "storagedrawers:remote_group_upgrade": "Storage Drawers remote group",
}


class StorageDrawersExtension:
    def matches(self, raw_type: str) -> bool:
        return normalize_recipe_type(raw_type).startswith(_STORAGE_DRAWERS_PREFIX)

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None:
        return None

    def skip_reason(self, data: dict[str, object]) -> str | None:
        return "synthetic in-game recipe"

    def display_name(self, raw_type: str) -> str:
        normalized = normalize_recipe_type(raw_type)
        return _DISPLAY_NAMES.get(
            normalized, normalized.split(":", 1)[-1].replace("_", " ").title()
        )


def storage_drawers_extension() -> CategoryExtension:
    return StorageDrawersExtension()
