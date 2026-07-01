from pydantic import BaseModel, Field

from app.schemas.canvas import CanvasGraph


class CalculateProductionRequest(BaseModel):
    target_item_id: str | None = None
    target_rate_per_minute: float | None = Field(default=None, gt=0)
    graph: CanvasGraph
    version: str = "26.2"
    profile_id: str | None = None
    include_mods: bool = True
    include_synthetic: bool = True


class ProductionStage(BaseModel):
    recipe_node_id: str
    recipe_id: str
    machine_id: str
    machine_count: float
    machine_limit_applied: bool = False
    input_rates: dict[str, float]
    output_rates: dict[str, float]


class ProductionPlan(BaseModel):
    target_item_id: str
    target_rate_per_minute: float
    effective_target_rate_per_minute: float
    stages: list[ProductionStage]
    total_raw_items: dict[str, float] = Field(default_factory=dict)
    constraint_errors: list[str] = Field(default_factory=list)
