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

    it('inlines factory sub-canvas recipes without synthetic terminal nodes', () => {
        const factoryNodes: CanvasNodeRecord[] = [
            {
                id: 'factory1',
                kind: 'outpost',
                x: 200,
                y: 0,
                machineName: 'Фабрика',
                inputs: [{ name: 'oak log', amount: 1, item_id: 'minecraft:oak_log' }],
                outputs: [{ name: 'stick', amount: 4, item_id: 'minecraft:stick' }],
                subCanvas: {
                    nodes: [
                        {
                            id: 'in1',
                            kind: 'factory_in',
                            x: 0,
                            y: 0,
                            machineName: 'Вход в фабрику',
                            inputs: [],
                            outputs: [
                                { name: 'oak log', amount: 1, item_id: 'minecraft:oak_log' },
                            ],
                        },
                        {
                            id: 'r_stick',
                            kind: 'recipe',
                            recipeId: 'minecraft:stick',
                            x: 50,
                            y: 0,
                            machineName: 'Верстак',
                            durationTicks: 100,
                            inputs: [
                                { name: 'oak log', amount: 1, item_id: 'minecraft:oak_log' },
                            ],
                            outputs: [{ name: 'stick', amount: 4, item_id: 'minecraft:stick' }],
                        },
                        {
                            id: 'out1',
                            kind: 'factory_out',
                            x: 100,
                            y: 0,
                            machineName: 'Выход из фабрики',
                            inputs: [{ name: 'stick', amount: 4, item_id: 'minecraft:stick' }],
                            outputs: [],
                        },
                    ],
                    connections: [
                        {
                            id: 'c-in-stick',
                            from: {
                                nodeId: 'in1',
                                slotType: 'output',
                                itemIndex: 0,
                                itemName: 'oak log',
                            },
                            to: {
                                nodeId: 'r_stick',
                                slotType: 'input',
                                itemIndex: 0,
                                itemName: 'oak log',
                            },
                        },
                        {
                            id: 'c-stick-out',
                            from: {
                                nodeId: 'r_stick',
                                slotType: 'output',
                                itemIndex: 0,
                                itemName: 'stick',
                            },
                            to: {
                                nodeId: 'out1',
                                slotType: 'input',
                                itemIndex: 0,
                                itemName: 'stick',
                            },
                        },
                    ],
                },
            },
        ];

        const graph = canvasToBackendGraph(factoryNodes, []);

        // Внутренний рецепт развёрнут (с namespace-префиксом ноды-фабрики).
        expect(graph.recipe_nodes).toHaveLength(1);
        expect(graph.recipe_nodes[0]?.recipe_id).toBe('minecraft:stick');
        expect(graph.recipe_nodes[0]?.node_id).toBe('factory1::r_stick');
        expect(graph.recipe_nodes[0]?.duration_ticks).toBe(100);

        // Ни сама фабрика, ни порты не уходят в backend как recipe-ноды.
        expect(graph.recipe_nodes.some((node) => node.kind === 'outpost')).toBe(false);
        expect(graph.recipe_nodes.some((node) => node.recipe_id.startsWith('outpost:'))).toBe(
            false,
        );

        // Вход подключён к рецепту, поэтому oak log не считается «сырым» входом.
        expect(graph.item_nodes.some((node) => node.item_id === 'minecraft:oak_log')).toBe(true);
        expect(
            graph.edges.some(
                (edge) =>
                    edge.target_node_id === 'factory1::r_stick' &&
                    edge.item_id === 'minecraft:oak_log',
            ),
        ).toBe(true);
    });
});
