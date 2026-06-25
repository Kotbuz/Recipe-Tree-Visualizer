from pydantic import BaseModel, Field

from app.schemas.canvas import CanvasGraph


class CalculateProductionRequest(BaseModel):
    target_item_id: str
    target_rate_per_minute: float = Field(gt=0)
    graph: CanvasGraph
    version: str = "26.2"
    include_mods: bool = True
    include_synthetic: bool = True


class ProductionStage(BaseModel):
    recipe_id: str
    machine_id: str
    machine_count: float
    input_rates: dict[str, float]
    output_rates: dict[str, float]


class ProductionPlan(BaseModel):
    target_item_id: str
    target_rate_per_minute: float
    stages: list[ProductionStage]
