from app.recipes.extensions.base import CategoryExtension, CategoryExtensionRegistry
from app.recipes.extensions.forge import forge_recipe_extension
from app.recipes.extensions.storagedrawers import storage_drawers_extension

_DEFAULT_EXTENSIONS: list[CategoryExtension] = [
    forge_recipe_extension(),
    storage_drawers_extension(),
]

_default_registry: CategoryExtensionRegistry | None = None


def default_category_extensions() -> CategoryExtensionRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = CategoryExtensionRegistry(_DEFAULT_EXTENSIONS)
    return _default_registry


__all__ = [
    "CategoryExtension",
    "CategoryExtensionRegistry",
    "default_category_extensions",
    "forge_recipe_extension",
    "storage_drawers_extension",
]
