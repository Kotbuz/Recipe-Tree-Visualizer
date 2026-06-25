from __future__ import annotations

import json
import zipfile
from pathlib import Path, PurePosixPath

import orjson

from app.core.config import get_settings
from app.recipes.ingredients import create_ingredient_resolver
from app.recipes.loaders.recipe_paths import (
    discover_recipe_file,
    jar_recipe_patterns_for_version,
    recipe_layout_for_version,
)
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import ProviderResult, SkippedRecipe
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe


class VanillaJarProvider:
    def __init__(
        self,
        parser: JsonRecipeParser | None = None,
        tag_loader: TagLoader | None = None,
    ) -> None:
        self._parser = parser
        self._tag_loader = tag_loader or TagLoader()

    def source_id(self) -> str:
        return "vanilla"

    def load(self, version: str) -> ProviderResult:
        recipe_dir = get_settings().minecraft_versions_path / version / "recipe"
        if recipe_dir.exists() and recipe_dir.is_dir():
            result = self._load_from_directory(recipe_dir, version)
            if result.recipes:
                return result

        if recipe_layout_for_version(version) == "jvm":
            return ProviderResult()

        jar_path = self.resolve_jar_path(version)
        if jar_path is not None:
            return self._load_from_jar(jar_path, version)

        return ProviderResult()

    def _build_parser(self, version: str, jar_path: Path) -> JsonRecipeParser:
        if self._parser is not None:
            return self._parser
        tag_members = self._tag_loader.load_from_jar(jar_path)
        resolver = create_ingredient_resolver(version, tag_members=tag_members)
        return JsonRecipeParser(resolver=resolver)

    def _load_from_directory(self, recipe_dir: Path, version: str) -> ProviderResult:
        recipes = ProviderResult()
        source = f"vanilla:{version}"
        parser = self._build_parser(version, self.resolve_jar_path(version) or recipe_dir)

        for json_file in sorted(recipe_dir.glob("*.json")):
            try:
                with json_file.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                recipes.skipped.append(
                    SkippedRecipe(
                        recipe_id=json_file.stem,
                        raw_type=None,
                        reason="invalid json",
                    )
                )
                continue

            if not isinstance(data, dict):
                continue

            recipe_id = f"minecraft:{json_file.stem}"
            try_add_recipe(
                parser,
                recipes,
                recipe_id,
                data,
                source=source,
                mod_id="minecraft",
            )

        return recipes

    def _load_from_jar(self, jar_path: Path, version: str) -> ProviderResult:
        recipes = ProviderResult()
        source = f"vanilla:{version}"
        parser = self._build_parser(version, jar_path)
        patterns = jar_recipe_patterns_for_version(version)

        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.namelist():
                    if not any(pattern.match(entry) for pattern in patterns):
                        continue

                    discovered = discover_recipe_file(entry)
                    if discovered is None or discovered.namespace != "minecraft":
                        continue

                    recipe_name = PurePosixPath(discovered.filename).stem
                    recipe_id = f"minecraft:{recipe_name}"
                    try:
                        raw = archive.read(discovered.filename)
                        data = orjson.loads(raw)
                    except (OSError, orjson.JSONDecodeError):
                        recipes.skipped.append(
                            SkippedRecipe(
                                recipe_id=recipe_id,
                                raw_type=None,
                                reason="invalid json",
                            )
                        )
                        continue

                    if not isinstance(data, dict):
                        continue

                    try_add_recipe(
                        parser,
                        recipes,
                        recipe_id,
                        data,
                        source=source,
                        mod_id="minecraft",
                    )
        except (OSError, zipfile.BadZipFile):
            return ProviderResult()

        return recipes

    def resolve_jar_path(self, version: str) -> Path | None:
        root = get_settings().minecraft_versions_path
        candidates = (
            root / f"{version}.jar",
            root / version / f"{version}.jar",
            root / version / "client.jar",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None
