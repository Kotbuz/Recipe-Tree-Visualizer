from __future__ import annotations

from app.parser.jar_reader import JarReader
from app.recipes.models import ProviderResult
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe


class ModJarProvider:
    def __init__(
        self,
        jar_reader: JarReader | None = None,
        parser: JsonRecipeParser | None = None,
    ) -> None:
        self._jar_reader = jar_reader or JarReader()
        self._parser = parser or JsonRecipeParser()

    def source_id(self) -> str:
        return "mod"

    def load(self, jar_path: str) -> ProviderResult:
        raw = self._jar_reader.read(jar_path)
        result = ProviderResult()
        source = f"mod:{raw.meta.mod_id}"

        for recipe_file in raw.recipe_files:
            try_add_recipe(
                self._parser,
                result,
                recipe_file.recipe_id,
                recipe_file.data,
                source=source,
                mod_id=raw.meta.mod_id,
            )

        return result
