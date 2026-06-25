from app.parser.models import RawModData
from app.recipes.models import ProviderResult
from app.schemas.domain import ModSummary


def build_mod_summary(raw: RawModData, result: ProviderResult) -> ModSummary:
    item_ids: set[str] = set()
    machine_ids: set[str] = set()

    for recipe in result.recipes:
        machine_ids.add(recipe.catalyst_id)
        for part in [*recipe.inputs, *recipe.outputs]:
            item_ids.add(part.item_id)

    return ModSummary(
        mod_id=raw.meta.mod_id,
        name=raw.meta.name,
        loader=raw.meta.loader.value,
        item_count=len(item_ids),
        recipe_count=len(result.recipes),
        machine_count=len(machine_ids),
        skipped_recipe_count=len(result.skipped),
    )
