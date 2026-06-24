from dataclasses import dataclass, field

from app.parser.loaders import ModLoader
from app.schemas.domain import Item, Machine, ModSummary, Recipe


@dataclass
class ModIndex:
    mod_id: str
    name: str
    loader: ModLoader
    items: dict[str, Item] = field(default_factory=dict)
    recipes: dict[str, Recipe] = field(default_factory=dict)
    machines: dict[str, Machine] = field(default_factory=dict)
    recipes_by_output: dict[str, list[str]] = field(default_factory=dict)
    skipped_recipe_count: int = 0

    def to_summary(self) -> ModSummary:
        return ModSummary(
            mod_id=self.mod_id,
            name=self.name,
            loader=self.loader.value,
            item_count=len(self.items),
            recipe_count=len(self.recipes),
            machine_count=len(self.machines),
            skipped_recipe_count=self.skipped_recipe_count,
        )


class ModRegistry:
    def __init__(self) -> None:
        self._mods: dict[str, ModIndex] = {}

    def list_mods(self) -> list[ModSummary]:
        return [mod.to_summary() for mod in self._mods.values()]

    def search_items(self, query: str, limit: int = 20) -> list[Item]:
        needle = query.casefold()
        results: list[Item] = []
        for mod in self._mods.values():
            for item in mod.items.values():
                if needle in item.name.casefold() or needle in item.id.casefold():
                    results.append(item)
                    if len(results) >= limit:
                        return results
        return results

    def get_recipes_for_item(self, item_id: str) -> list[Recipe]:
        recipes: list[Recipe] = []
        for mod in self._mods.values():
            for recipe_id in mod.recipes_by_output.get(item_id, []):
                recipe = mod.recipes.get(recipe_id)
                if recipe is not None:
                    recipes.append(recipe)
        return recipes

    def register(self, index: ModIndex) -> ModSummary:
        self._mods[index.mod_id] = index
        return index.to_summary()


registry = ModRegistry()
