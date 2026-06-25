from __future__ import annotations

from app.recipes.models import ProviderResult
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.recipes.synthetic import (
    build_anvil_repair_recipes,
    build_brewing_recipes,
    build_compost_recipes,
)


class SyntheticProvider:
    def __init__(self, vanilla_provider: VanillaJarProvider | None = None) -> None:
        self._vanilla_provider = vanilla_provider or VanillaJarProvider()

    def source_id(self) -> str:
        return "synthetic"

    def load(self, version: str) -> ProviderResult:
        source = f"synthetic:{version}"
        jar_path = self._vanilla_provider.resolve_jar_path(version)

        recipes = [
            *build_brewing_recipes(source=source),
            *build_compost_recipes(source=source),
            *build_anvil_repair_recipes(source=source, jar_path=jar_path),
        ]
        return ProviderResult(recipes=recipes)
