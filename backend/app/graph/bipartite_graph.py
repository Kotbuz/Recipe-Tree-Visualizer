from __future__ import annotations

from collections import defaultdict

from app.calculator.constants import DEFAULT_OPERATION_TICKS
from app.graph.errors import GraphValidationError
from app.recipes.adapters import item_id_to_display_name
from app.recipes.manager import _focus_lookup_keys, recipe_manager
from app.recipes.models import Recipe
from app.recipes.registry import IngredientRegistry, get_profile_ingredient_registry
from app.schemas.canvas import CanvasGraph, CanvasItemNode, CanvasRecipeNode
from app.services.item_matching import items_match
from app.services.mod_service import mod_service

_TERMINAL_RECIPE_KINDS = frozenset({"chest", "outpost"})


class BipartiteGraphEngine:
    def __init__(
        self,
        graph: CanvasGraph,
        version: str = "26.2",
        *,
        profile_id: str | None = None,
        include_mods: bool = True,
        include_synthetic: bool = True,
    ) -> None:
        self._graph = graph
        self._version = version
        self._profile_id = profile_id
        self._include_mods = include_mods
        self._include_synthetic = include_synthetic
        self._registry: IngredientRegistry | None = None
        if include_mods:
            mod_service.ensure_version_mods_loaded(version, profile_id=profile_id)
        self._recipes_by_id = self._load_recipes()
        self._item_nodes: dict[str, CanvasItemNode] = {
            node.node_id: node for node in graph.item_nodes
        }
        self._recipe_nodes: dict[str, CanvasRecipeNode] = {
            node.node_id: node for node in graph.recipe_nodes
        }
        self._match_cache: dict[tuple[str, str], bool] = {}
        self._producer_node_cache: dict[str, str | None] = {}
        self._output_producers_index = self._build_output_producers_index()

    @property
    def registry(self) -> IngredientRegistry:
        if self._registry is None:
            self._registry = get_profile_ingredient_registry(
                self._version,
                self._profile_id,
            )
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

    def validate_acyclic_from_target(self, target_item_id: str) -> None:
        visiting_recipe_nodes: set[str] = set()

        def visit_item(item_id: str) -> None:
            recipe_node_id = self.select_producer_recipe_node(item_id)
            if recipe_node_id is None:
                return
            visit_recipe(recipe_node_id)

        def visit_recipe(recipe_node_id: str) -> None:
            if recipe_node_id in visiting_recipe_nodes:
                raise GraphValidationError("Production graph contains a cycle")
            visiting_recipe_nodes.add(recipe_node_id)
            recipe = self.get_recipe_for_node(recipe_node_id)
            for recipe_input in recipe.inputs:
                visit_item(recipe_input.item_id)
            visiting_recipe_nodes.remove(recipe_node_id)

        visit_item(target_item_id)

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

    def get_canvas_recipe_node(self, recipe_node_id: str) -> CanvasRecipeNode:
        recipe_node = self._recipe_nodes.get(recipe_node_id)
        if recipe_node is None:
            raise GraphValidationError(f"Unknown recipe node: {recipe_node_id}")
        return recipe_node

    def items_match(self, needle: str, candidate: str) -> bool:
        return self._item_matches(needle, candidate)

    def duration_ticks_for_node(self, recipe_node_id: str) -> int:
        recipe_node = self._recipe_nodes.get(recipe_node_id)
        if recipe_node is None:
            raise GraphValidationError(f"Unknown recipe node: {recipe_node_id}")

        if recipe_node.duration_ticks is not None and recipe_node.duration_ticks > 0:
            return recipe_node.duration_ticks

        recipe = self.get_recipe(recipe_node.recipe_id)
        if recipe.duration_ticks is not None and recipe.duration_ticks > 0:
            return recipe.duration_ticks

        return DEFAULT_OPERATION_TICKS

    def producer_recipe_nodes_for(self, item_id: str) -> list[str]:
        producers: list[str] = []
        seen: set[str] = set()
        for key in _focus_lookup_keys(item_id):
            for recipe_node_id in self._output_producers_index.get(key, ()):
                if recipe_node_id in seen:
                    continue
                recipe = self.get_recipe_for_node(recipe_node_id)
                if any(self._item_matches(item_id, output.item_id) for output in recipe.outputs):
                    producers.append(recipe_node_id)
                    seen.add(recipe_node_id)
        return producers

    def connected_producer_recipe_nodes_for(self, item_id: str) -> list[str]:
        producers: list[str] = []
        for recipe_node in self._graph.recipe_nodes:
            if not self._is_production_recipe_node(recipe_node):
                continue
            recipe = self.get_recipe(recipe_node.recipe_id)
            if not any(self._item_matches(item_id, output.item_id) for output in recipe.outputs):
                continue
            for edge in self._graph.edges:
                if edge.source_node_id != recipe_node.node_id:
                    continue
                if edge.target_node_id not in self._item_nodes:
                    continue
                target_item = self._item_nodes[edge.target_node_id].item_id
                if self._item_matches(item_id, target_item) and self._item_matches(
                    item_id, edge.item_id
                ):
                    producers.append(recipe_node.node_id)
                    break
        return producers

    def select_producer_recipe_node(self, item_id: str) -> str | None:
        cached = self._producer_node_cache.get(item_id)
        if item_id in self._producer_node_cache:
            return cached

        connected = self.connected_producer_recipe_nodes_for(item_id)
        if len(connected) > 1:
            raise GraphValidationError(
                f"Multiple connected recipes produce {item_id}; disconnect alternatives on canvas"
            )
        if len(connected) == 1:
            self._producer_node_cache[item_id] = connected[0]
            return connected[0]

        fallback = self.producer_recipe_nodes_for(item_id)
        if len(fallback) > 1:
            raise GraphValidationError(
                f"Multiple recipes produce {item_id}; connect one recipe to the item node"
            )
        result = fallback[0] if len(fallback) == 1 else None
        self._producer_node_cache[item_id] = result
        return result

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

    def input_per_craft(
        self,
        recipe: Recipe,
        item_id: str,
        recipe_node_id: str,
    ) -> float:
        edge_amount = self._edge_input_amount(recipe_node_id, item_id)
        if edge_amount is not None:
            return edge_amount

        for recipe_input in recipe.inputs:
            if self._item_matches(item_id, recipe_input.item_id):
                return recipe_input.amount

        raise GraphValidationError(
            f"Recipe {recipe.id} does not consume {item_id} for node {recipe_node_id}"
        )

    def has_upstream_recipe(self, item_id: str) -> bool:
        return self.select_producer_recipe_node(item_id) is not None

    def connected_input_items_for(self, recipe_node_id: str, ingredient_id: str) -> list[str]:
        items: list[str] = []
        for edge in self._graph.edges:
            if edge.target_node_id != recipe_node_id:
                continue
            if edge.source_node_id not in self._item_nodes:
                continue
            source_item = self._item_nodes[edge.source_node_id].item_id
            if not self._item_matches(ingredient_id, source_item):
                continue
            if not self._item_matches(ingredient_id, edge.item_id):
                continue
            if source_item not in items:
                items.append(source_item)
        return items

    def _load_recipes(self) -> dict[str, Recipe]:
        needed_ids = {node.recipe_id for node in self._graph.recipe_nodes}
        if not needed_ids:
            return {}

        bundle = recipe_manager.get_recipe_bundle(
            self._version,
            profile_id=self._profile_id,
            include_mods=self._include_mods,
            include_synthetic=self._include_synthetic,
        )
        return {
            recipe_id: bundle.recipes_by_id[recipe_id]
            for recipe_id in needed_ids
            if recipe_id in bundle.recipes_by_id
        }

    def _build_output_producers_index(self) -> dict[str, tuple[str, ...]]:
        index: dict[str, set[str]] = defaultdict(set)
        for recipe_node in self._graph.recipe_nodes:
            if not self._is_production_recipe_node(recipe_node):
                continue
            recipe = self._recipes_by_id.get(recipe_node.recipe_id)
            if recipe is None:
                continue
            for output in recipe.outputs:
                index[output.item_id.lower()].add(recipe_node.node_id)
                for key in _focus_lookup_keys(output.item_id):
                    index[key].add(recipe_node.node_id)
        return {key: tuple(sorted(values)) for key, values in index.items()}

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

    def _edge_input_amount(self, recipe_node_id: str, item_id: str) -> float | None:
        for edge in self._graph.edges:
            if edge.target_node_id != recipe_node_id:
                continue
            if edge.source_node_id not in self._item_nodes:
                continue
            source_item = self._item_nodes[edge.source_node_id].item_id
            if not self._item_matches(item_id, source_item):
                continue
            if not self._item_matches(item_id, edge.item_id):
                continue
            return edge.amount
        return None

    @staticmethod
    def _is_production_recipe_node(recipe_node: CanvasRecipeNode) -> bool:
        return recipe_node.kind not in _TERMINAL_RECIPE_KINDS

    def _item_matches(self, needle: str, candidate: str) -> bool:
        cache_key = (needle, candidate)
        cached = self._match_cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._item_matches_uncached(needle, candidate)
        self._match_cache[cache_key] = result
        return result

    def _item_matches_uncached(self, needle: str, candidate: str) -> bool:
        if needle == candidate:
            return True

        needle_lower = needle.lower()
        candidate_lower = candidate.lower()
        if needle_lower == candidate_lower:
            return True

        if items_match(needle_lower, item_id_to_display_name(candidate)):
            return True
        if items_match(needle_lower, item_id_to_display_name(needle)):
            return True

        if needle.startswith("tag:"):
            return candidate in self.registry.resolve_tag(needle)
        if candidate.startswith("tag:"):
            return needle in self.registry.resolve_tag(candidate)

        return self.registry.ingredient_matches(needle, candidate)
