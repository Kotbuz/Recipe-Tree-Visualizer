from app.recipes.category import display_name_for_raw_type
from app.recipes.models import Recipe
from app.schemas.recipe_file import RecipeItem, RecipeSummary


def item_id_to_display_name(item_id: str) -> str:
    raw = item_id.removeprefix("tag:")
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return raw.replace("_", " ")


def to_recipe_summary(recipe: Recipe) -> RecipeSummary:
    machine_type = recipe.raw_type or recipe.recipe_type.value
    return RecipeSummary(
        recipe_id=recipe.id,
        machine_type=machine_type,
        machine_name=display_name_for_raw_type(machine_type),
        inputs=[
            RecipeItem(
                name=item_id_to_display_name(part.item_id),
                amount=int(part.amount),
                item_id=part.item_id,
            )
            for part in recipe.inputs
        ],
        outputs=[
            RecipeItem(
                name=item_id_to_display_name(part.item_id),
                amount=int(part.amount),
                item_id=part.item_id,
            )
            for part in recipe.outputs
        ],
    )
