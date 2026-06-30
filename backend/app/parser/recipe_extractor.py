from app.parser.exceptions import JarParseError
from app.parser.models import RawRecipeFile
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.schemas.domain import Recipe, RecipeIO


class RecipeExtractor:
    def __init__(self, parser: JsonRecipeParser | None = None) -> None:
        self._parser = parser or JsonRecipeParser()

    def can_extract(self, recipe_file: RawRecipeFile) -> bool:
        data = recipe_file.data
        if not self._parser.can_parse(data):
            return False
        return not self._parser.skip_reason(data)

    def extract(self, recipe_file: RawRecipeFile, mod_id: str) -> Recipe:
        parsed = self._parser.parse(
            recipe_file.recipe_id,
            recipe_file.data,
            source=f"mod:{mod_id}",
            mod_id=mod_id,
        )
        if parsed is None:
            recipe_type = recipe_file.data.get("type")
            raise JarParseError(f"Unsupported recipe type: {recipe_type}")

        return Recipe(
            id=parsed.id,
            machine_id=parsed.catalyst_id,
            inputs=[RecipeIO(item_id=part.item_id, amount=part.amount) for part in parsed.inputs],
            outputs=[RecipeIO(item_id=part.item_id, amount=part.amount) for part in parsed.outputs],
            duration_ticks=parsed.duration_ticks,
            mod_id=mod_id,
        )
