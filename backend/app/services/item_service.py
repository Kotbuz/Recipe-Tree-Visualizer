from __future__ import annotations

from app.indexer.mod_registry import registry
from app.recipes.focus import RecipeIngredientRole
from app.recipes.manager import recipe_manager
from app.recipes.registry import Ingredient, get_version_ingredient_registry
from app.schemas.domain import Item
from app.schemas.items import ItemRecipesResponse, ItemSearchResponse


class ItemService:
    def search_items(
        self,
        query: str,
        version: str = "26.2",
        limit: int = 20,
    ) -> ItemSearchResponse:
        ingredient_registry = get_version_ingredient_registry(version)
        items: list[Item] = []
        seen: set[str] = set()

        for ingredient in ingredient_registry.search(query, limit=limit):
            item = self._ingredient_to_item(ingredient)
            items.append(item)
            seen.add(item.id)

        for mod_item in registry.search_items(query, limit=limit):
            if mod_item.id in seen:
                continue
            items.append(mod_item)
            seen.add(mod_item.id)
            if len(items) >= limit:
                break

        return ItemSearchResponse(query=query, items=items[:limit])

    def get_item_recipes(
        self,
        item_id: str,
        version: str = "26.2",
        *,
        include_mods: bool = True,
    ) -> ItemRecipesResponse:
        recipes = (
            recipe_manager.lookup(version, include_mods=include_mods)
            .focus(item_id, RecipeIngredientRole.OUTPUT)
            .summaries()
        )
        return ItemRecipesResponse(item_id=item_id, recipes=recipes)

    @staticmethod
    def _ingredient_to_item(ingredient: Ingredient) -> Item:
        if ingredient.id.startswith("tag:"):
            mod_id = ingredient.id.removeprefix("tag:").split(":", 1)[0]
        else:
            mod_id = ingredient.id.split(":", maxsplit=1)[0]
        return Item(
            id=ingredient.id,
            name=ingredient.display_name,
            icon=ingredient.icon_id,
            mod_id=mod_id,
        )


item_service = ItemService()
