from __future__ import annotations

from functools import lru_cache

from app.recipes.ingredients import create_ingredient_resolver
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import ProviderResult, Recipe, SkippedRecipe
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe
from app.recipes.providers.kubejs_custom_machinery_parser import parse_custom_machinery_scripts
from app.recipes.providers.kubejs_script_models import KubejsScriptResult
from app.recipes.providers.kubejs_script_parser import (
    apply_kubejs_removes,
    parse_kubejs_server_scripts,
)
from app.services.version_service import version_service


class KubejsScriptProvider:
    def __init__(
        self,
        parser: JsonRecipeParser | None = None,
        tag_loader: TagLoader | None = None,
    ) -> None:
        self._parser = parser
        self._tag_loader = tag_loader or TagLoader()

    def source_id(self) -> str:
        return "kubejs_scripts"

    def load(self, version: str, profile_id: str) -> KubejsScriptResult:
        scripts_dir = version_service.kubejs_dir(version, profile_id) / "server_scripts"
        parsed = parse_kubejs_server_scripts(scripts_dir)
        result = KubejsScriptResult(
            removes=parsed.removes,
            dynamic_expressions=parsed.dynamic_expressions,
        )

        cm_recipes = parse_custom_machinery_scripts(scripts_dir)
        result.recipes.extend(cm_recipes)

        if not parsed.recipe_payloads and not parsed.removes and not cm_recipes:
            return result

        if not parsed.recipe_payloads:
            return result

        parser = self._parser or self._build_parser(version, profile_id)
        source = f"kubejs_scripts:{profile_id}"

        for payload in parsed.recipe_payloads:
            recipe_id = payload.pop("__recipe_id", None)
            source_file = payload.pop("__source_file", None)
            if not isinstance(recipe_id, str) or not recipe_id.strip():
                raw_type = payload.get("type")
                result.skipped.append(
                    SkippedRecipe(
                        recipe_id="<anonymous>",
                        raw_type=raw_type if isinstance(raw_type, str) else None,
                        reason="kubejs script recipe missing .id()",
                    )
                )
                continue

            mod_id = recipe_id.split(":", 1)[0]
            provider_result = ProviderResult()
            try_add_recipe(
                parser,
                provider_result,
                recipe_id,
                payload,
                source=f"{source}:{source_file}" if source_file else source,
                mod_id=mod_id,
            )
            result.recipes.extend(provider_result.recipes)
            result.skipped.extend(provider_result.skipped)

        return result

    def _build_parser(self, version: str, profile_id: str) -> JsonRecipeParser:
        mods_dir = version_service.mods_dir(version, profile_id)
        tag_maps = []
        if mods_dir.is_dir():
            for jar_path in sorted(mods_dir.glob("*.jar")):
                tag_maps.append(self._tag_loader.load_from_jar(jar_path))
        tag_members = self._tag_loader.merge_tag_maps(*tag_maps) if tag_maps else {}
        resolver = create_ingredient_resolver(version, tag_members=tag_members)
        return JsonRecipeParser(resolver=resolver)


@lru_cache(maxsize=32)
def load_kubejs_script_changes(version: str, profile_id: str) -> KubejsScriptResult:
    return KubejsScriptProvider().load(version, profile_id)


def clear_kubejs_script_cache() -> None:
    load_kubejs_script_changes.cache_clear()


def apply_script_changes_to_recipes(
    merged: dict[str, Recipe],
    script_result: KubejsScriptResult,
) -> tuple[int, int]:
    removed_count = len(apply_kubejs_removes(merged, script_result.removes))
    added_count = 0
    for recipe in script_result.recipes:
        merged[recipe.id] = recipe
        added_count += 1
    return removed_count, added_count
