from __future__ import annotations

from app.graph.errors import GraphValidationError
from app.recipes.manager import recipe_manager
from app.recipes.models import Recipe
from app.recipes.registry import IngredientRegistry, get_version_ingredient_registry
from app.schemas.canvas import CanvasGraph, CanvasItemNode, CanvasRecipeNode


class BipartiteGraphEngine:
    def __init__(
        self,
        graph: CanvasGraph,
        version: str = "26.2",
        *,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> None:
        self._graph = graph
        self._version = version
        self._include_mods = include_mods
        self._include_synthetic = include_synthetic
        self._registry = get_version_ingredient_registry(version)
        self._recipes_by_id = self._load_recipes()
        self._item_nodes: dict[str, CanvasItemNode] = {
            node.node_id: node for node in graph.item_nodes
        }
        self._recipe_nodes: dict[str, CanvasRecipeNode] = {
            node.node_id: node for node in graph.recipe_nodes
        }

    @property
    def registry(self) -> IngredientRegistry:
        return self._registry

    def validate(self) -> None:
        node_ids = set(self._item_nodes) | set(self._recipe_nodes)
        if len(node_ids) != len(self._graph.item_nodes) + len(self._graph.recipe_nodes):
            raise GraphValidationError("Duplicate node_id in graph")

        for recipe_node in self._graph.recipe_nodes:
            if recipe_node.recipe_id not in self._recipes_by_id:
                raise GraphValidationError(f"Unknown recipe_id: {recipe_node.recipe_id}")

        for edge in self._graph.edges:
            if edge.source_node_id not in node_ids:
                raise GraphValidationError(f"Unknown edge source: {edge.source_node_id}")
            if edge.target_node_id not in node_ids:
                raise GraphValidationError(f"Unknown edge target: {edge.target_node_id}")

            source_is_item = edge.source_node_id in self._item_nodes
            source_is_recipe = edge.source_node_id in self._recipe_nodes
            target_is_item = edge.target_node_id in self._item_nodes
            target_is_recipe = edge.target_node_id in self._recipe_nodes

            if source_is_item == target_is_item:
                raise GraphValidationError(
                    f"Edge {edge.edge_id} must connect an item node and a recipe node"
                )
            if not (source_is_item or source_is_recipe) or not (target_is_item or target_is_recipe):
                raise GraphValidationError(f"Edge {edge.edge_id} references invalid nodes")

    def get_recipe(self, recipe_id: str) -> Recipe:
        recipe = self._recipes_by_id.get(recipe_id)
        if recipe is None:
            raise GraphValidationError(f"Unknown recipe_id: {recipe_id}")
        return recipe

    def get_recipe_for_node(self, recipe_node_id: str) -> Recipe:
        recipe_node = self._recipe_nodes.get(recipe_node_id)
        if recipe_node is None:
            raise GraphValidationError(f"Unknown recipe node: {recipe_node_id}")
        return self.get_recipe(recipe_node.recipe_id)

    def producer_recipe_nodes_for(self, item_id: str) -> list[str]:
        producers: list[str] = []
        for recipe_node in self._graph.recipe_nodes:
            recipe = self.get_recipe(recipe_node.recipe_id)
            if any(self._item_matches(item_id, output.item_id) for output in recipe.outputs):
                producers.append(recipe_node.node_id)
        return producers

    def output_per_craft(self, recipe: Recipe, item_id: str, recipe_node_id: str) -> float:
        edge_amount = self._edge_output_amount(recipe_node_id, item_id)
        if edge_amount is not None:
            return edge_amount

        for output in recipe.outputs:
            if self._item_matches(item_id, output.item_id):
                return output.amount

        raise GraphValidationError(
            f"Recipe {recipe.id} does not output {item_id} for node {recipe_node_id}"
        )

    def has_upstream_recipe(self, item_id: str) -> bool:
        return bool(self.producer_recipe_nodes_for(item_id))

    def _load_recipes(self) -> dict[str, Recipe]:
        recipes = recipe_manager.get_version_recipes(
            self._version,
            include_mods=self._include_mods,
            include_synthetic=self._include_synthetic,
        )
        return {recipe.id: recipe for recipe in recipes}

    def _edge_output_amount(self, recipe_node_id: str, item_id: str) -> float | None:
        for edge in self._graph.edges:
            if edge.source_node_id != recipe_node_id:
                continue
            if edge.target_node_id not in self._item_nodes:
                continue
            if not self._item_matches(item_id, edge.item_id):
                continue
            return edge.amount
        return None

    def _item_matches(self, needle: str, candidate: str) -> bool:
        if needle == candidate:
            return True
        if self._registry.ingredient_matches(needle, candidate):
            return True
        if self._registry.ingredient_matches(candidate, needle):
            return True
        if needle.startswith("tag:"):
            return candidate in self._registry.resolve_tag(needle)
        if candidate.startswith("tag:"):
            return needle in self._registry.resolve_tag(candidate)
        return False
