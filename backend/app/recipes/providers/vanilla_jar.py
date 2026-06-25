from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from app.core.config import get_settings
from app.recipes.models import ProviderResult, SkippedRecipe
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser

RECIPE_PATH = re.compile(r"^data/([^/]+)/recipes?/(.+\.json)$")
ADVANCEMENT_SEGMENT = "/advancement/"


class VanillaJarProvider:
    def __init__(self, parser: JsonRecipeParser | None = None) -> None:
        self._parser = parser or JsonRecipeParser()

    def source_id(self) -> str:
        return "vanilla"

    def load(self, version: str) -> ProviderResult:
        recipe_dir = get_settings().minecraft_versions_path / version / "recipe"
        if recipe_dir.exists() and recipe_dir.is_dir():
            result = self._load_from_directory(recipe_dir, version)
            if result.recipes:
                return result

        jar_path = self.resolve_jar_path(version)
        if jar_path is not None:
            return self._load_from_jar(jar_path, version)

        return ProviderResult()

    def _load_from_directory(self, recipe_dir: Path, version: str) -> ProviderResult:
        recipes = ProviderResult()
        source = f"vanilla:{version}"

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
            self._try_add_recipe(recipes, recipe_id, data, source=source, mod_id="minecraft")

        return recipes

    def _load_from_jar(self, jar_path: Path, version: str) -> ProviderResult:
        recipes = ProviderResult()
        source = f"vanilla:{version}"

        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.namelist():
                    if ADVANCEMENT_SEGMENT in entry:
                        continue
                    match = RECIPE_PATH.match(entry)
                    if not match:
                        continue
                    namespace, relative_path = match.groups()
                    if namespace != "minecraft":
                        continue

                    recipe_name = PurePosixPath(relative_path).stem
                    recipe_id = f"{namespace}:{recipe_name}"
                    try:
                        raw = archive.read(entry)
                        data = json.loads(raw)
                    except (OSError, json.JSONDecodeError):
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

                    self._try_add_recipe(recipes, recipe_id, data, source=source, mod_id="minecraft")
        except (OSError, zipfile.BadZipFile):
            return ProviderResult()

        return recipes

    def _try_add_recipe(
        self,
        result: ProviderResult,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str,
    ) -> None:
        raw_type = data.get("type")
        if not self._parser.can_parse(data):
            result.skipped.append(
                SkippedRecipe(
                    recipe_id=recipe_id,
                    raw_type=raw_type if isinstance(raw_type, str) else None,
                    reason="unsupported or invalid recipe",
                )
            )
            return

        recipe = self._parser.parse(recipe_id, data, source=source, mod_id=mod_id)
        if recipe is None:
            result.skipped.append(
                SkippedRecipe(
                    recipe_id=recipe_id,
                    raw_type=raw_type if isinstance(raw_type, str) else None,
                    reason="parse failed",
                )
            )
            return

        result.recipes.append(recipe)

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
