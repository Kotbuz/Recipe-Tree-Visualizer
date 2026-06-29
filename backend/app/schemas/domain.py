from enum import StrEnum

from pydantic import BaseModel, Field


class RecipeIODirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class RecipeIO(BaseModel):
    item_id: str
    amount: float = Field(gt=0)
    chance: float | None = Field(default=None, ge=0, le=1)
    metadata: int | None = None


class Item(BaseModel):
    id: str
    name: str
    icon: str
    mod_id: str


class Machine(BaseModel):
    id: str
    name: str
    icon: str
    speed: float = 1.0
    mod_id: str


class Recipe(BaseModel):
    id: str
    machine_id: str
    inputs: list[RecipeIO]
    outputs: list[RecipeIO]
    duration_ticks: int | None = None
    duration_seconds: float | None = None
    energy_cost: float | None = None
    probability: float | None = None
    mod_id: str


class ModSummary(BaseModel):
    mod_id: str
    name: str
    loader: str = "unknown"
    minecraft_version: str | None = None
    minecraft_version_range: str | None = None
    jar_filename: str | None = None
    compatible: bool | None = None
    item_count: int = 0
    recipe_count: int = 0
    machine_count: int = 0
    skipped_recipe_count: int = 0
