from __future__ import annotations

from app.graph.bipartite_graph import BipartiteGraphEngine
from app.graph.errors import GraphValidationError
from app.recipes.models import Recipe
from app.schemas.canvas import CanvasGraph
from app.schemas.graph import CalculateProductionRequest, ProductionPlan, ProductionStage

_CRAFTS_PER_MACHINE_PER_MINUTE = 60.0
_TICKS_PER_SECOND = 20.0


class ProductionCalculator:
    def calculate(self, request: CalculateProductionRequest) -> ProductionPlan:
        engine = BipartiteGraphEngine(
            request.graph,
            request.version,
            include_mods=request.include_mods,
            include_synthetic=request.include_synthetic,
        )
        self.validate_graph(request.graph, engine=engine)

        stages: list[ProductionStage] = []
        visited_recipe_nodes: set[str] = set()
        self._plan_item(
            engine,
            request.target_item_id,
            request.target_rate_per_minute,
            stages,
            visited_recipe_nodes,
        )

        if not stages:
            raise GraphValidationError(
                f"No recipe in graph produces {request.target_item_id}"
            )

        return ProductionPlan(
            target_item_id=request.target_item_id,
            target_rate_per_minute=request.target_rate_per_minute,
            stages=stages,
        )

    def validate_graph(
        self,
        graph: CanvasGraph,
        *,
        engine: BipartiteGraphEngine | None = None,
    ) -> None:
        active_engine = engine or BipartiteGraphEngine(graph)
        active_engine.validate()

    def _plan_item(
        self,
        engine: BipartiteGraphEngine,
        item_id: str,
        rate_per_minute: float,
        stages: list[ProductionStage],
        visited_recipe_nodes: set[str],
    ) -> None:
        producer_nodes = engine.producer_recipe_nodes_for(item_id)
        if not producer_nodes:
            return

        recipe_node_id = producer_nodes[0]
        if recipe_node_id in visited_recipe_nodes:
            return
        visited_recipe_nodes.add(recipe_node_id)

        recipe = engine.get_recipe_for_node(recipe_node_id)
        output_per_craft = engine.output_per_craft(recipe, item_id, recipe_node_id)
        crafts_per_minute = rate_per_minute / output_per_craft
        machine_throughput = self._machine_throughput_per_minute(recipe)
        machine_count = crafts_per_minute / machine_throughput

        input_rates: dict[str, float] = {}
        for recipe_input in recipe.inputs:
            input_rate = crafts_per_minute * recipe_input.amount
            input_rates[recipe_input.item_id] = (
                input_rates.get(recipe_input.item_id, 0.0) + input_rate
            )

        output_rates = {
            output.item_id: crafts_per_minute * output.amount for output in recipe.outputs
        }

        stages.append(
            ProductionStage(
                recipe_id=recipe.id,
                machine_id=recipe.catalyst_id,
                machine_count=machine_count,
                input_rates=input_rates,
                output_rates=output_rates,
            )
        )

        for recipe_input in recipe.inputs:
            input_rate = input_rates[recipe_input.item_id]
            if engine.has_upstream_recipe(recipe_input.item_id):
                self._plan_item(
                    engine,
                    recipe_input.item_id,
                    input_rate,
                    stages,
                    visited_recipe_nodes,
                )

    @staticmethod
    def _machine_throughput_per_minute(recipe: Recipe) -> float:
        if recipe.duration_ticks is None or recipe.duration_ticks <= 0:
            return _CRAFTS_PER_MACHINE_PER_MINUTE

        seconds_per_craft = recipe.duration_ticks / _TICKS_PER_SECOND
        return 60.0 / seconds_per_craft
