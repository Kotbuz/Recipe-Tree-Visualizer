from __future__ import annotations

from pathlib import Path

from app.parser.jar_reader import JarReader
from app.recipes.ingredients import create_ingredient_resolver
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import ProviderResult
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe


class ModJarProvider:
    def __init__(
        self,
        jar_reader: JarReader | None = None,
        parser: JsonRecipeParser | None = None,
        tag_loader: TagLoader | None = None,
    ) -> None:
        self._jar_reader = jar_reader or JarReader()
        self._parser = parser
        self._tag_loader = tag_loader or TagLoader()

    def source_id(self) -> str:
        return "mod"

    def load(self, jar_path: str, *, version: str | None = None) -> ProviderResult:
        raw = self._jar_reader.read(jar_path)
        parser = self._parser or self._build_parser(version, jar_path)
        result = ProviderResult()
        source = f"mod:{raw.meta.mod_id}"

        for recipe_file in raw.recipe_files:
            try_add_recipe(
                parser,
                result,
                recipe_file.recipe_id,
                recipe_file.data,
                source=source,
                mod_id=raw.meta.mod_id,
            )

        return result

    def _build_parser(self, version: str | None, jar_path: str) -> JsonRecipeParser:
        if not version:
            return JsonRecipeParser()
        tag_members = self._tag_loader.load_from_jar(Path(jar_path))
        resolver = create_ingredient_resolver(version, tag_members=tag_members)
        return JsonRecipeParser(resolver=resolver)
