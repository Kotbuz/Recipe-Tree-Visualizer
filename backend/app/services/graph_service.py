from app.calculator.production_calculator import ProductionCalculator
from app.indexer.mod_registry import ModRegistry, registry
from app.schemas.graph import CalculateProductionRequest, ProductionPlan
from app.schemas.items import ItemRecipesResponse, ItemSearchResponse


class GraphService:
    def __init__(
        self,
        mod_registry: ModRegistry,
        calculator: ProductionCalculator,
    ) -> None:
        self._registry = mod_registry
        self._calculator = calculator

    def search_items(self, query: str, limit: int = 20) -> ItemSearchResponse:
        return ItemSearchResponse(query=query, items=self._registry.search_items(query, limit))

    def get_item_recipes(self, item_id: str) -> ItemRecipesResponse:
        return ItemRecipesResponse(
            item_id=item_id, recipes=self._registry.get_recipes_for_item(item_id)
        )

    def calculate_production(self, request: CalculateProductionRequest) -> ProductionPlan:
        return self._calculator.calculate(request)


graph_service = GraphService(registry, ProductionCalculator())
