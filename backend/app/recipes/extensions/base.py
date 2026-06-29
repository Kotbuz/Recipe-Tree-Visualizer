from __future__ import annotations

from typing import Protocol

from app.recipes.models import Recipe


class CategoryExtension(Protocol):
    def matches(self, raw_type: str) -> bool: ...

    def parse(
        self,
        recipe_id: str,
        data: dict[str, object],
        *,
        source: str,
        mod_id: str | None,
    ) -> Recipe | None: ...

    def skip_reason(self, data: dict[str, object]) -> str | None: ...


class CategoryExtensionRegistry:
    def __init__(self, extensions: list[CategoryExtension] | None = None) -> None:
        self._extensions = list(extensions or [])

    def find(self, raw_type: str) -> CategoryExtension | None:
        for extension in self._extensions:
            if extension.matches(raw_type):
                return extension
        return None

    def matches(self, raw_type: str) -> bool:
        return self.find(raw_type) is not None

    def display_name(self, raw_type: str) -> str | None:
        extension = self.find(raw_type)
        if extension is None:
            return None
        get_display_name = getattr(extension, "display_name", None)
        if callable(get_display_name):
            return get_display_name(raw_type)
        return None
