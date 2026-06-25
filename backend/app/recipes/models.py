from dataclasses import dataclass, field

from app.recipes.types import RecipeType


@dataclass(frozen=True)
class RecipeIO:
    item_id: str
    amount: float
    chance: float | None = None


@dataclass(frozen=True)
class Recipe:
    id: str
    recipe_type: RecipeType
    category_id: str
    catalyst_id: str
    inputs: list[RecipeIO]
    outputs: list[RecipeIO]
    duration_ticks: int | None
    source: str
    mod_id: str | None = None
    raw_type: str = ""


@dataclass(frozen=True)
class SkippedRecipe:
    recipe_id: str
    raw_type: str | None
    reason: str


@dataclass
class ProviderResult:
    recipes: list[Recipe] = field(default_factory=list)
    skipped: list[SkippedRecipe] = field(default_factory=list)
