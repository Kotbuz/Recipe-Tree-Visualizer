from typing import Protocol

from app.recipes.models import ProviderResult


class RecipeProvider(Protocol):
    def source_id(self) -> str: ...

    def load(self, version: str) -> ProviderResult: ...
