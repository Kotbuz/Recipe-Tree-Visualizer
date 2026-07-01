from __future__ import annotations

from loguru import logger

from app.calculator.constants import TICKS_PER_SECOND
from app.calculator.machine_speed import machine_speed
from app.graph.bipartite_graph import BipartiteGraphEngine
from app.graph.errors import GraphValidationError
from app.recipes.models import Recipe
from app.schemas.canvas import CanvasGraph, CanvasRecipeNode
from app.schemas.graph import CalculateProductionRequest, ProductionPlan, ProductionStage


class ProductionCalculator:
    def calculate(self, request: CalculateProductionRequest) -> ProductionPlan:
        engine = BipartiteGraphEngine(
            request.graph,
            request.version,
            profile_id=request.profile_id,
            include_mods=request.include_mods,
            include_synthetic=request.include_synthetic,
        )
        self.validate_graph(request.graph, engine=engine)

        target_item_id, target_rate, constraint_errors = self._resolve_target(
            request,
            engine,
        )
        engine.validate_acyclic_from_target(target_item_id)

        stages: list[ProductionStage] = []
        visited_recipe_nodes: set[str] = set()
        self._plan_item(
            engine,
            target_item_id,
            target_rate,
            stages,
            visited_recipe_nodes,
            constraint_errors,
        )

        if not stages:
            raise GraphValidationError(f"No recipe in graph produces {target_item_id}")

        effective_rate = self._effective_output_rate(engine, stages, target_item_id)
        total_raw_items = self._collect_raw_items(engine, stages)
        logger.info(
            "Production plan for {} @ {}/min (effective {}): {} stages, {} raw inputs",
            target_item_id,
            target_rate,
            effective_rate,
            len(stages),
            len(total_raw_items),
        )

        return ProductionPlan(
            target_item_id=target_item_id,
            target_rate_per_minute=target_rate,
            effective_target_rate_per_minute=effective_rate,
            stages=stages,
            total_raw_items=total_raw_items,
            constraint_errors=constraint_errors,
        )

    def validate_graph(
        self,
        graph: CanvasGraph,
        *,
        engine: BipartiteGraphEngine | None = None,
    ) -> None:
        active_engine = engine or BipartiteGraphEngine(graph)
        active_engine.validate()

    def _resolve_target(
        self,
        request: CalculateProductionRequest,
        engine: BipartiteGraphEngine,
    ) -> tuple[str, float, list[str]]:
        constraint_errors: list[str] = []
        if request.target_item_id and request.target_rate_per_minute:
            return request.target_item_id, request.target_rate_per_minute, constraint_errors

        limited_nodes = [
            node
            for node in request.graph.recipe_nodes
            if node.machine_limit is not None and self._is_production_node(node)
        ]
        if not limited_nodes:
            raise GraphValidationError(
                "Укажите целевую скорость выхода или лимит машин хотя бы на одном рецепте",
            )

        anchor = limited_nodes[0]
        recipe = engine.get_recipe_for_node(anchor.node_id)
        if not recipe.outputs:
            raise GraphValidationError(
                f"Recipe node {anchor.node_id} has no outputs for anchor calculation",
            )

        primary_output = recipe.outputs[0]
        throughput = self._machine_throughput_per_minute(engine, anchor.node_id, recipe)
        output_per_craft = engine.output_per_craft(
            recipe,
            primary_output.item_id,
            anchor.node_id,
        )
        rate = anchor.machine_limit * throughput * output_per_craft
        return primary_output.item_id, rate, constraint_errors

    def _plan_item(
        self,
        engine: BipartiteGraphEngine,
        item_id: str,
        rate_per_minute: float,
        stages: list[ProductionStage],
        visited_recipe_nodes: set[str],
        constraint_errors: list[str],
    ) -> None:
        recipe_node_id = engine.select_producer_recipe_node(item_id)
        if recipe_node_id is None:
            return

        if recipe_node_id in visited_recipe_nodes:
            return
        visited_recipe_nodes.add(recipe_node_id)

        recipe = engine.get_recipe_for_node(recipe_node_id)
        recipe_node = engine.get_canvas_recipe_node(recipe_node_id)

        rate_per_minute = self._apply_output_rate_limit(
            recipe_node,
            item_id,
            rate_per_minute,
            constraint_errors,
            recipe_node_id,
        )

        output_per_craft = engine.output_per_craft(recipe, item_id, recipe_node_id)
        crafts_per_minute = rate_per_minute / output_per_craft
        machine_throughput = self._machine_throughput_per_minute(engine, recipe_node_id, recipe)
        machine_count_needed = crafts_per_minute / machine_throughput

        machine_limit_applied = False
        machine_count = machine_count_needed
        if recipe_node.machine_limit is not None:
            if machine_count_needed > recipe_node.machine_limit + 1e-9:
                machine_count = float(recipe_node.machine_limit)
                crafts_per_minute = machine_count * machine_throughput
                machine_limit_applied = True
                constraint_errors.append(
                    f"Лимит машин ({recipe_node.machine_limit}) на узле {recipe_node_id}: "
                    f"требовалось {machine_count_needed:.2f}",
                )
            else:
                machine_count = machine_count_needed

        if recipe_node.auto_round and recipe_node.machine_limit is None:
            rounded = max(1.0, round(machine_count))
            if abs(rounded - machine_count) > 1e-9:
                machine_count = rounded
                crafts_per_minute = machine_count * machine_throughput

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
                recipe_node_id=recipe_node_id,
                recipe_id=recipe.id,
                machine_id=recipe.catalyst_id,
                machine_count=machine_count,
                machine_limit_applied=machine_limit_applied,
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
                        constraint_errors,
                    )

    @staticmethod
    def _apply_output_rate_limit(
        recipe_node: CanvasRecipeNode,
        item_id: str,
        rate_per_minute: float,
        constraint_errors: list[str],
        recipe_node_id: str,
    ) -> float:
        limit = recipe_node.output_rate_limit_per_minute
        if limit is None:
            return rate_per_minute
        if rate_per_minute > limit + 1e-9:
            constraint_errors.append(
                f"Лимит скорости ({limit:.2f}/мин) на узле {recipe_node_id} "
                f"для {item_id}: запрошено {rate_per_minute:.2f}/мин",
            )
            return limit
        return rate_per_minute

    @staticmethod
    def _effective_output_rate(
        engine: BipartiteGraphEngine,
        stages: list[ProductionStage],
        target_item_id: str,
    ) -> float:
        for stage in stages:
            for item_id, rate in stage.output_rates.items():
                if engine.items_match(item_id, target_item_id):
                    return rate
        return 0.0

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
    def _machine_throughput_per_minute(
        engine: BipartiteGraphEngine,
        recipe_node_id: str,
        recipe: Recipe,
    ) -> float:
        recipe_node = engine.get_canvas_recipe_node(recipe_node_id)
        duration_ticks = engine.duration_ticks_for_node(recipe_node_id)
        speed_factor = recipe_node.speed_percent / 100.0
        effective_ticks = duration_ticks / speed_factor if speed_factor > 0 else duration_ticks
        seconds_per_craft = effective_ticks / TICKS_PER_SECOND
        base_throughput = 60.0 / seconds_per_craft
        return base_throughput * machine_speed(recipe.catalyst_id)

    @staticmethod
    def _is_production_node(node: CanvasRecipeNode) -> bool:
        return node.kind not in {"chest", "outpost", "factory_in", "factory_out"}
