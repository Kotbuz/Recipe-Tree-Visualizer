from __future__ import annotations

from app.recipes.ingredients import create_ingredient_resolver
from app.recipes.loaders.tag_loader import TagLoader
from app.recipes.models import ProviderResult
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser
from app.recipes.providers.jar_recipe_loader import try_add_recipe
from app.recipes.providers.kubejs_paths import (
    is_kubejs_recipe_enabled,
    iter_kubejs_recipe_files,
    load_json_object,
    skipped_recipe,
)
from app.services.version_service import version_service


class KubejsDataProvider:
    def __init__(
        self,
        parser: JsonRecipeParser | None = None,
        tag_loader: TagLoader | None = None,
    ) -> None:
        self._parser = parser
        self._tag_loader = tag_loader or TagLoader()

    def source_id(self) -> str:
        return "kubejs"

    def load(self, version: str, profile_id: str) -> ProviderResult:
        kubejs_dir = version_service.kubejs_dir(version, profile_id)
        if not kubejs_dir.is_dir():
            return ProviderResult()

        parser = self._parser or self._build_parser(version, profile_id)
        result = ProviderResult()
        source = f"kubejs:{profile_id}"

        for recipe_id, file_path in iter_kubejs_recipe_files(kubejs_dir):
            data = load_json_object(file_path)
            if data is None:
                result.skipped.append(
                    skipped_recipe(recipe_id, None, f"invalid json: {file_path.name}")
                )
                continue
            if not is_kubejs_recipe_enabled(data):
                result.skipped.append(
                    skipped_recipe(recipe_id, _raw_type(data), "disabled by recipe condition")
                )
                continue

            namespace = file_path.relative_to(kubejs_dir / "data").parts[0]
            try_add_recipe(
                parser,
                result,
                recipe_id,
                data,
                source=source,
                mod_id=namespace,
            )

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


def _raw_type(data: dict[str, object]) -> str | None:
    raw_type = data.get("type")
    return raw_type if isinstance(raw_type, str) else None
