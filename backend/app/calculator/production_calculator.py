from app.schemas.canvas import CanvasGraph
from app.schemas.graph import CalculateProductionRequest, ProductionPlan


class ProductionCalculator:
    def calculate(self, request: CalculateProductionRequest) -> ProductionPlan:
        raise NotImplementedError("Production calculation is not implemented yet")

    def validate_graph(self, graph: CanvasGraph) -> None:
        raise NotImplementedError("Graph validation is not implemented yet")
