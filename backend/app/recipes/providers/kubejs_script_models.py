from __future__ import annotations

from dataclasses import dataclass, field

from app.recipes.models import Recipe, SkippedRecipe


@dataclass(frozen=True)
class KubejsRecipeRemove:
    recipe_id: str | None = None
    output_item_id: str | None = None
    mod_id: str | None = None
    recipe_type: str | None = None
    source_file: str | None = None


@dataclass
class KubejsScriptParseResult:
    removes: list[KubejsRecipeRemove] = field(default_factory=list)
    recipe_payloads: list[dict[str, object]] = field(default_factory=list)
    dynamic_expressions: int = 0


@dataclass
class KubejsScriptResult:
    removes: list[KubejsRecipeRemove] = field(default_factory=list)
    recipes: list[Recipe] = field(default_factory=list)
    skipped: list[SkippedRecipe] = field(default_factory=list)
    dynamic_expressions: int = 0
