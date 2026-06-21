from loguru import logger

from app.indexer.mod_registry import ModIndex
from app.parser.item_builder import build_item
from app.parser.models import RawModData
from app.parser.recipe_extractor import RecipeExtractor
from app.schemas.domain import Machine, Recipe

DEFAULT_MACHINES: dict[str, tuple[str, str]] = {
    "minecraft:crafting_table": ("Crafting Table", "minecraft:crafting_table"),
    "minecraft:furnace": ("Furnace", "minecraft:furnace"),
    "minecraft:blast_furnace": ("Blast Furnace", "minecraft:blast_furnace"),
    "minecraft:smoker": ("Smoker", "minecraft:smoker"),
    "minecraft:campfire": ("Campfire", "minecraft:campfire"),
    "minecraft:stonecutter": ("Stonecutter", "minecraft:stonecutter"),
}


class ModIndexer:
    def __init__(self, recipe_extractor: RecipeExtractor | None = None) -> None:
        self._recipe_extractor = recipe_extractor or RecipeExtractor()

    def build(self, raw: RawModData) -> ModIndex:
        index = ModIndex(
            mod_id=raw.meta.mod_id,
            name=raw.meta.name,
            loader=raw.meta.loader,
        )
        for recipe_file in raw.recipe_files:
            if not self._recipe_extractor.can_extract(recipe_file):
                index.skipped_recipe_count += 1
                recipe_type = recipe_file.data.get("type")
                logger.info(
                    "Skipping unsupported recipe {} (type={})",
                    recipe_file.recipe_id,
                    recipe_type,
                )
                continue

            recipe = self._recipe_extractor.extract(recipe_file, raw.meta.mod_id)
            index.recipes[recipe.id] = recipe
            self._register_machine(index, recipe.machine_id)
            self._register_recipe_output(index, recipe)
            for part in [*recipe.inputs, *recipe.outputs]:
                self._register_item(index, part.item_id, raw)

        return index

    def _register_machine(self, index: ModIndex, machine_id: str) -> None:
        if machine_id in index.machines:
            return
        default = (machine_id.split(":")[-1].title(), machine_id)
        label, icon = DEFAULT_MACHINES.get(machine_id, default)
        namespace = machine_id.split(":", maxsplit=1)[0]
        index.machines[machine_id] = Machine(
            id=machine_id,
            name=label,
            icon=icon,
            mod_id=namespace,
        )

    def _register_recipe_output(self, index: ModIndex, recipe: Recipe) -> None:
        for output in recipe.outputs:
            index.recipes_by_output.setdefault(output.item_id, []).append(recipe.id)

    def _register_item(self, index: ModIndex, item_id: str, raw: RawModData) -> None:
        if item_id in index.items:
            return
        namespace = item_id.split(":", maxsplit=1)[0]
        mod_id = namespace if not item_id.startswith("tag:") else raw.meta.mod_id
        index.items[item_id] = build_item(item_id, mod_id, raw.texture_paths)
