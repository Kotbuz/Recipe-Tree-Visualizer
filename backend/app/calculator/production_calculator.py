from __future__ import annotations

from loguru import logger

from app.calculator.machine_speed import machine_speed
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
        engine.validate_acyclic_from_target(request.target_item_id)

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

        total_raw_items = self._collect_raw_items(engine, stages)
        logger.info(
            "Production plan for {} @ {}/min: {} stages, {} raw inputs",
            request.target_item_id,
            request.target_rate_per_minute,
            len(stages),
            len(total_raw_items),
        )

        return ProductionPlan(
            target_item_id=request.target_item_id,
            target_rate_per_minute=request.target_rate_per_minute,
            stages=stages,
            total_raw_items=total_raw_items,
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
        recipe_node_id = engine.select_producer_recipe_node(item_id)
        if recipe_node_id is None:
            return

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
            amount_per_craft = engine.input_per_craft(
                recipe,
                recipe_input.item_id,
                recipe_node_id,
            )
            input_rate = crafts_per_minute * amount_per_craft
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
            upstream_items = engine.connected_input_items_for(
                recipe_node_id,
                recipe_input.item_id,
            )
            if not upstream_items and engine.has_upstream_recipe(recipe_input.item_id):
                upstream_items = [recipe_input.item_id]

            for upstream_item_id in upstream_items:
                if engine.has_upstream_recipe(upstream_item_id):
                    self._plan_item(
                        engine,
                        upstream_item_id,
                        input_rate,
                        stages,
                        visited_recipe_nodes,
                    )

    @staticmethod
    def _collect_raw_items(
        engine: BipartiteGraphEngine,
        stages: list[ProductionStage],
    ) -> dict[str, float]:
        raw_items: dict[str, float] = {}
        for stage in stages:
            for item_id, rate in stage.input_rates.items():
                if engine.has_upstream_recipe(item_id):
                    continue
                raw_items[item_id] = raw_items.get(item_id, 0.0) + rate
        return raw_items

    @staticmethod
    def _machine_throughput_per_minute(recipe: Recipe) -> float:
        if recipe.duration_ticks is None or recipe.duration_ticks <= 0:
            base_throughput = _CRAFTS_PER_MACHINE_PER_MINUTE
        else:
            seconds_per_craft = recipe.duration_ticks / _TICKS_PER_SECOND
            base_throughput = 60.0 / seconds_per_craft

        return base_throughput * machine_speed(recipe.catalyst_id)
