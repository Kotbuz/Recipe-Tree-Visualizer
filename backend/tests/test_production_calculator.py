from unittest.mock import patch

import pytest
from app.calculator.machine_speed import machine_speed
from app.calculator.production_calculator import ProductionCalculator
from app.graph.bipartite_graph import BipartiteGraphEngine
from app.graph.errors import GraphValidationError
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType
from app.schemas.canvas import CanvasEdge, CanvasGraph, CanvasItemNode, CanvasRecipeNode
from app.schemas.graph import CalculateProductionRequest
from app.services.recipe_service import _resolve_vanilla_jar_path


def _require_vanilla_jar(version: str = "26.2") -> None:
    if _resolve_vanilla_jar_path(version) is None:
        pytest.skip(f"No vanilla jar found for version {version}")


def _mock_recipes(*recipes: Recipe) -> dict[str, Recipe]:
    return {recipe.id: recipe for recipe in recipes}


def _stick_recipe() -> Recipe:
    return Recipe(
        id="minecraft:stick",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="minecraft:crafting_shaped",
        catalyst_id="minecraft:crafting_table",
        inputs=[RecipeIO(item_id="minecraft:oak_planks", amount=2.0)],
        outputs=[RecipeIO(item_id="minecraft:stick", amount=4.0)],
        duration_ticks=None,
        source="test",
    )


def _planks_recipe() -> Recipe:
    return Recipe(
        id="minecraft:oak_planks",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="minecraft:crafting_shaped",
        catalyst_id="minecraft:crafting_table",
        inputs=[RecipeIO(item_id="minecraft:oak_log", amount=1.0)],
        outputs=[RecipeIO(item_id="minecraft:oak_planks", amount=4.0)],
        duration_ticks=None,
        source="test",
    )


def _smelting_recipe() -> Recipe:
    return Recipe(
        id="minecraft:iron_ingot_from_smelting",
        recipe_type=RecipeType.SMELTING,
        category_id="minecraft:smelting",
        catalyst_id="minecraft:furnace",
        inputs=[RecipeIO(item_id="minecraft:iron_ore", amount=1.0)],
        outputs=[RecipeIO(item_id="minecraft:iron_ingot", amount=1.0)],
        duration_ticks=200,
        source="test",
    )


def _fast_furnace_recipe() -> Recipe:
    return Recipe(
        id="testmod:iron_ingot_electric",
        recipe_type=RecipeType.SMELTING,
        category_id="minecraft:smelting",
        catalyst_id="testmod:electric_furnace",
        inputs=[RecipeIO(item_id="minecraft:iron_ore", amount=1.0)],
        outputs=[RecipeIO(item_id="minecraft:iron_ingot", amount=1.0)],
        duration_ticks=200,
        source="test",
    )


def _stick_chain_graph() -> CanvasGraph:
    return CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_stick", item_id="minecraft:stick"),
            CanvasItemNode(node_id="item_planks", item_id="minecraft:oak_planks"),
            CanvasItemNode(node_id="item_log", item_id="minecraft:oak_log"),
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
            CanvasEdge(
                edge_id="in_log",
                source_node_id="item_log",
                target_node_id="recipe_planks",
                item_id="minecraft:oak_log",
                amount=1,
            ),
        ],
    )


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


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_plans_stick_chain(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_stick_recipe(), _planks_recipe())
    graph = _stick_chain_graph()

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
    assert plan.stages[0].input_rates["minecraft:oak_planks"] == pytest.approx(50)
    assert plan.stages[1].recipe_id == "minecraft:oak_planks"
    assert plan.total_raw_items["minecraft:oak_log"] == pytest.approx(12.5)


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_plans_smelting(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_smelting_recipe())
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_ingot", item_id="minecraft:iron_ingot"),
            CanvasItemNode(node_id="item_ore", item_id="minecraft:iron_ore"),
        ],
        recipe_nodes=[
            CanvasRecipeNode(
                node_id="recipe_smelt",
                recipe_id="minecraft:iron_ingot_from_smelting",
            ),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_ingot",
                source_node_id="recipe_smelt",
                target_node_id="item_ingot",
                item_id="minecraft:iron_ingot",
                amount=1,
            ),
            CanvasEdge(
                edge_id="in_ore",
                source_node_id="item_ore",
                target_node_id="recipe_smelt",
                item_id="minecraft:iron_ore",
                amount=1,
            ),
        ],
    )

    plan = ProductionCalculator().calculate(
        CalculateProductionRequest(
            target_item_id="minecraft:iron_ingot",
            target_rate_per_minute=60,
            graph=graph,
        )
    )

    assert len(plan.stages) == 1
    assert plan.stages[0].machine_count == pytest.approx(10.0)
    assert plan.stages[0].input_rates["minecraft:iron_ore"] == pytest.approx(60)
    assert plan.total_raw_items["minecraft:iron_ore"] == pytest.approx(60)


@patch.object(BipartiteGraphEngine, "_load_recipes")
@patch(
    "app.calculator.production_calculator.machine_speed",
    side_effect=lambda catalyst_id: 2.0 if catalyst_id == "testmod:electric_furnace" else 1.0,
)
def test_production_calculator_applies_machine_speed(mock_speed, mock_load) -> None:
    mock_load.return_value = _mock_recipes(_fast_furnace_recipe())
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_ingot", item_id="minecraft:iron_ingot"),
            CanvasItemNode(node_id="item_ore", item_id="minecraft:iron_ore"),
        ],
        recipe_nodes=[
            CanvasRecipeNode(node_id="recipe_smelt", recipe_id="testmod:iron_ingot_electric"),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_ingot",
                source_node_id="recipe_smelt",
                target_node_id="item_ingot",
                item_id="minecraft:iron_ingot",
                amount=1,
            ),
            CanvasEdge(
                edge_id="in_ore",
                source_node_id="item_ore",
                target_node_id="recipe_smelt",
                item_id="minecraft:iron_ore",
                amount=1,
            ),
        ],
    )

    plan = ProductionCalculator().calculate(
        CalculateProductionRequest(
            target_item_id="minecraft:iron_ingot",
            target_rate_per_minute=60,
            graph=graph,
        )
    )

    assert plan.stages[0].machine_count == pytest.approx(5.0)


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_rejects_cycle(mock_load) -> None:
    recipe_a = Recipe(
        id="test:make_x",
        recipe_type=RecipeType.CRAFTING_SHAPELESS,
        category_id="minecraft:crafting_shapeless",
        catalyst_id="minecraft:crafting_table",
        inputs=[RecipeIO(item_id="test:item_y", amount=1.0)],
        outputs=[RecipeIO(item_id="test:item_x", amount=1.0)],
        duration_ticks=None,
        source="test",
    )
    recipe_b = Recipe(
        id="test:make_y",
        recipe_type=RecipeType.CRAFTING_SHAPELESS,
        category_id="minecraft:crafting_shapeless",
        catalyst_id="minecraft:crafting_table",
        inputs=[RecipeIO(item_id="test:item_x", amount=1.0)],
        outputs=[RecipeIO(item_id="test:item_y", amount=1.0)],
        duration_ticks=None,
        source="test",
    )
    mock_load.return_value = _mock_recipes(recipe_a, recipe_b)
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_x", item_id="test:item_x"),
            CanvasItemNode(node_id="item_y", item_id="test:item_y"),
        ],
        recipe_nodes=[
            CanvasRecipeNode(node_id="recipe_x", recipe_id="test:make_x"),
            CanvasRecipeNode(node_id="recipe_y", recipe_id="test:make_y"),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_x",
                source_node_id="recipe_x",
                target_node_id="item_x",
                item_id="test:item_x",
                amount=1,
            ),
            CanvasEdge(
                edge_id="in_y",
                source_node_id="item_y",
                target_node_id="recipe_x",
                item_id="test:item_y",
                amount=1,
            ),
            CanvasEdge(
                edge_id="out_y",
                source_node_id="recipe_y",
                target_node_id="item_y",
                item_id="test:item_y",
                amount=1,
            ),
            CanvasEdge(
                edge_id="in_x",
                source_node_id="item_x",
                target_node_id="recipe_y",
                item_id="test:item_x",
                amount=1,
            ),
        ],
    )

    with pytest.raises(GraphValidationError, match="cycle"):
        ProductionCalculator().calculate(
            CalculateProductionRequest(
                target_item_id="test:item_x",
                target_rate_per_minute=10,
                graph=graph,
            )
        )


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_rejects_multiple_connected_producers(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_stick_recipe(), _planks_recipe())
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_stick", item_id="minecraft:stick"),
            CanvasItemNode(node_id="item_planks", item_id="minecraft:oak_planks"),
        ],
        recipe_nodes=[
            CanvasRecipeNode(node_id="recipe_stick_a", recipe_id="minecraft:stick"),
            CanvasRecipeNode(node_id="recipe_stick_b", recipe_id="minecraft:stick"),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_a",
                source_node_id="recipe_stick_a",
                target_node_id="item_stick",
                item_id="minecraft:stick",
                amount=4,
            ),
            CanvasEdge(
                edge_id="out_b",
                source_node_id="recipe_stick_b",
                target_node_id="item_stick",
                item_id="minecraft:stick",
                amount=4,
            ),
            CanvasEdge(
                edge_id="in_planks",
                source_node_id="item_planks",
                target_node_id="recipe_stick_a",
                item_id="minecraft:oak_planks",
                amount=2,
            ),
        ],
    )

    with pytest.raises(GraphValidationError, match="Multiple connected recipes"):
        ProductionCalculator().calculate(
            CalculateProductionRequest(
                target_item_id="minecraft:stick",
                target_rate_per_minute=10,
                graph=graph,
            )
        )


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_skips_terminal_recipe_nodes(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_stick_recipe())
    graph = CanvasGraph(
        item_nodes=[CanvasItemNode(node_id="item_stick", item_id="minecraft:stick")],
        recipe_nodes=[
            CanvasRecipeNode(
                node_id="recipe_chest",
                recipe_id="minecraft:stick",
                kind="chest",
            ),
        ],
        edges=[
            CanvasEdge(
                edge_id="out_stick",
                source_node_id="recipe_chest",
                target_node_id="item_stick",
                item_id="minecraft:stick",
                amount=4,
            ),
        ],
    )

    with pytest.raises(GraphValidationError, match="No recipe in graph produces"):
        ProductionCalculator().calculate(
            CalculateProductionRequest(
                target_item_id="minecraft:stick",
                target_rate_per_minute=10,
                graph=graph,
            )
        )


def test_production_calculator_rejects_empty_graph() -> None:
    with pytest.raises(GraphValidationError, match="No recipe in graph produces"):
        ProductionCalculator().calculate(
            CalculateProductionRequest(
                target_item_id="minecraft:stick",
                target_rate_per_minute=10,
                graph=CanvasGraph(),
            )
        )


def test_production_calculator_plans_stick_chain_with_vanilla_jar() -> None:
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


def test_machine_speed_defaults_to_one() -> None:
    assert machine_speed("unknown:machine") == 1.0


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_duration_ticks_for_node_resolution(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_stick_recipe(), _smelting_recipe())
    engine = BipartiteGraphEngine(
        CanvasGraph(
            recipe_nodes=[
                CanvasRecipeNode(node_id="craft", recipe_id="minecraft:stick"),
                CanvasRecipeNode(
                    node_id="smelt",
                    recipe_id="minecraft:iron_ingot_from_smelting",
                    duration_ticks=150,
                ),
            ],
        )
    )

    assert engine.duration_ticks_for_node("craft") == 100
    assert engine.duration_ticks_for_node("smelt") == 150


@patch.object(BipartiteGraphEngine, "_load_recipes")
def test_production_calculator_uses_default_duration_for_crafting(mock_load) -> None:
    mock_load.return_value = _mock_recipes(_stick_recipe())
    graph = CanvasGraph(
        item_nodes=[
            CanvasItemNode(node_id="item_stick", item_id="minecraft:stick"),
            CanvasItemNode(node_id="item_planks", item_id="minecraft:oak_planks"),
        ],
        recipe_nodes=[CanvasRecipeNode(node_id="recipe_stick", recipe_id="minecraft:stick")],
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
        ],
    )

    plan = ProductionCalculator().calculate(
        CalculateProductionRequest(
            target_item_id="minecraft:stick",
            target_rate_per_minute=120,
            graph=graph,
        )
    )

    # 120 sticks/min = 30 crafts/min; default 100 ticks => 12 crafts/min per table
    assert plan.stages[0].machine_count == pytest.approx(2.5)
