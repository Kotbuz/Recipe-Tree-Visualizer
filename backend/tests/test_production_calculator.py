from app.calculator.production_calculator import ProductionCalculator
from app.graph.bipartite_graph import BipartiteGraphEngine
from app.graph.errors import GraphValidationError
from app.schemas.canvas import CanvasEdge, CanvasGraph, CanvasItemNode, CanvasRecipeNode
from app.schemas.graph import CalculateProductionRequest
from app.services.recipe_service import _resolve_vanilla_jar_path
import pytest


def _require_vanilla_jar(version: str = "26.2") -> None:
    if _resolve_vanilla_jar_path(version) is None:
        pytest.skip(f"No vanilla jar found for version {version}")


def test_bipartite_graph_rejects_unknown_recipe() -> None:
    graph = CanvasGraph(
        recipe_nodes=[CanvasRecipeNode(node_id="r1", recipe_id="minecraft:missing_recipe")],
    )
    engine = BipartiteGraphEngine(graph)

    with pytest.raises(GraphValidationError, match="Unknown recipe_id"):
        engine.validate()


def test_bipartite_graph_rejects_item_to_item_edge() -> None:
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="i1", item_id="minecraft:stick"),
            CanvasItemNode(node_id="i2", item_id="minecraft:oak_planks"),
        ],
        edges=[
            CanvasEdge(
                edge_id="e1",
                source_node_id="i1",
                target_node_id="i2",
                item_id="minecraft:stick",
                amount=1,
            )
        ],
    )
    engine = BipartiteGraphEngine(graph)

    with pytest.raises(GraphValidationError, match="item node and a recipe node"):
        engine.validate()


def test_production_calculator_plans_stick_chain() -> None:
    _require_vanilla_jar()
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_stick", item_id="minecraft:stick"),
            CanvasItemNode(node_id="item_planks", item_id="minecraft:oak_planks"),
        ],
        recipe_nodes=[
            CanvasRecipeNode(node_id="recipe_stick", recipe_id="minecraft:stick"),
            CanvasRecipeNode(node_id="recipe_planks", recipe_id="minecraft:oak_planks"),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_stick",
                source_node_id="recipe_stick",
                target_node_id="item_stick",
                item_id="minecraft:stick",
                amount=4,
            ),
            CanvasEdge(
                edge_id="in_planks",
                source_node_id="item_planks",
                target_node_id="recipe_stick",
                item_id="minecraft:oak_planks",
                amount=2,
            ),
            CanvasEdge(
                edge_id="out_planks",
                source_node_id="recipe_planks",
                target_node_id="item_planks",
                item_id="minecraft:oak_planks",
                amount=4,
            ),
        ],
    )

    plan = ProductionCalculator().calculate(
        CalculateProductionRequest(
            target_item_id="minecraft:stick",
            target_rate_per_minute=100,
            graph=graph,
            version="26.2",
        )
    )

    assert plan.target_rate_per_minute == 100
    assert len(plan.stages) == 2
    assert plan.stages[0].recipe_id == "minecraft:stick"
    assert plan.stages[0].machine_id == "minecraft:crafting_table"
    assert plan.stages[0].output_rates["minecraft:stick"] == pytest.approx(100)
    assert plan.stages[0].input_rates["tag:minecraft:planks"] == pytest.approx(50)
    assert plan.stages[1].recipe_id == "minecraft:oak_planks"


def test_production_calculator_rejects_empty_graph() -> None:
    with pytest.raises(GraphValidationError, match="No recipe in graph produces"):
        ProductionCalculator().calculate(
            CalculateProductionRequest(
                target_item_id="minecraft:stick",
                target_rate_per_minute=10,
                graph=CanvasGraph(),
            )
        )
