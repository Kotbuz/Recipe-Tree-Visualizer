from pydantic import BaseModel, Field

from app.schemas.domain import RecipeIO


class CanvasItemNode(BaseModel):
    node_id: str
    item_id: str
    amount: float = Field(default=1, gt=0)
    x: float = 0
    y: float = 0


class CanvasRecipeNode(BaseModel):
    node_id: str
    recipe_id: str
    kind: str | None = None
    duration_ticks: int | None = None
    machine_limit: int | None = Field(default=None, ge=1)
    output_rate_limit_per_minute: float | None = Field(default=None, gt=0)
    speed_percent: float = Field(default=100.0, gt=0)
    auto_round: bool = False
    x: float = 0
    y: float = 0


class CanvasEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    item_id: str
    amount: float = Field(gt=0)


class CanvasGraph(BaseModel):
    item_nodes: list[CanvasItemNode] = Field(default_factory=list)
    recipe_nodes: list[CanvasRecipeNode] = Field(default_factory=list)
    edges: list[CanvasEdge] = Field(default_factory=list)


class RecipeNodeDetail(BaseModel):
    node_id: str
    recipe_id: str
    machine_id: str
    inputs: list[RecipeIO]
    outputs: list[RecipeIO]
    duration_seconds: float | None = None
