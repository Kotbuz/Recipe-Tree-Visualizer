import { describe, expect, it } from 'vitest';

import { canvasToBackendGraph } from './canvasToBackendGraph';
import type { CanvasNodeRecord } from './canvasSchema';
import type { RecipeConnection } from '../types/recipe';

const stickNodes: CanvasNodeRecord[] = [
    {
        id: 'recipe_stick',
        kind: 'recipe',
        recipeId: 'minecraft:stick',
        x: 100,
        y: 100,
        machineName: 'Верстак',
        durationTicks: 100,
        inputs: [{ name: 'oak planks', amount: 2, item_id: 'minecraft:oak_planks' }],
        outputs: [{ name: 'stick', amount: 4, item_id: 'minecraft:stick' }],
    },
    {
        id: 'recipe_planks',
        kind: 'recipe',
        recipeId: 'minecraft:oak_planks',
        x: 0,
        y: 100,
        machineName: 'Верстак',
        durationTicks: 100,
        inputs: [{ name: 'oak log', amount: 1, item_id: 'minecraft:oak_log' }],
        outputs: [{ name: 'oak planks', amount: 4, item_id: 'minecraft:oak_planks' }],
    },
];

const stickConnections: RecipeConnection[] = [
    {
        id: 'conn-planks-stick',
        from: {
            nodeId: 'recipe_planks',
            slotType: 'output',
            itemIndex: 0,
            itemName: 'oak planks',
        },
        to: {
            nodeId: 'recipe_stick',
            slotType: 'input',
            itemIndex: 0,
            itemName: 'oak planks',
        },
    },
];

describe('canvasToBackendGraph', () => {
    it('converts recipe nodes and item junctions for a simple chain', () => {
        const graph = canvasToBackendGraph(stickNodes, stickConnections);

        expect(graph.recipe_nodes).toHaveLength(2);
        expect(graph.recipe_nodes[0]?.duration_ticks).toBe(100);
        expect(graph.item_nodes.some((node) => node.item_id === 'minecraft:oak_planks')).toBe(true);
        expect(graph.edges).toEqual(
            expect.arrayContaining([
                expect.objectContaining({
                    source_node_id: 'recipe_planks',
                    item_id: 'minecraft:oak_planks',
                }),
                expect.objectContaining({
                    target_node_id: 'recipe_stick',
                    item_id: 'minecraft:oak_planks',
                }),
            ]),
        );
    });

    it('creates raw item nodes for unconnected inputs', () => {
        const graph = canvasToBackendGraph(stickNodes, stickConnections);

        expect(
            graph.item_nodes.some(
                (node) =>
                    node.item_id === 'minecraft:oak_log' &&
                    graph.edges.some(
                        (edge) =>
                            edge.source_node_id === node.node_id &&
                            edge.target_node_id === 'recipe_planks',
                    ),
            ),
        ).toBe(true);
    });
});
