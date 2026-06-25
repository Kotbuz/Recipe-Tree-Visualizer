from app.calculator.production_calculator import ProductionCalculator
from app.schemas.graph import CalculateProductionRequest, ProductionPlan
from app.services.item_service import item_service


class GraphService:
    def __init__(self, calculator: ProductionCalculator) -> None:
        self._calculator = calculator

    def search_items(self, query: str, version: str = "26.2", limit: int = 20):
        return item_service.search_items(query, version=version, limit=limit)

    def get_item_recipes(
        self,
        item_id: str,
        version: str = "26.2",
        *,
        include_mods: bool = True,
    ):
        return item_service.get_item_recipes(item_id, version=version, include_mods=include_mods)

    def calculate_production(self, request: CalculateProductionRequest) -> ProductionPlan:
        return self._calculator.calculate(request)


graph_service = GraphService(ProductionCalculator())
