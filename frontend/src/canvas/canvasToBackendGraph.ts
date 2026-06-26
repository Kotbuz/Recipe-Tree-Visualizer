import type { CanvasNodeRecord } from './canvasSchema';
import { isSlotConnected } from './slotConnections';
import type { RecipeConnection, RecipeItem, SlotType } from '../types/recipe';

export class CanvasConversionError extends Error {}

export type BackendCanvasGraph = {
    item_nodes: Array<{
        node_id: string;
        item_id: string;
        amount: number;
        x: number;
        y: number;
    }>;
    recipe_nodes: Array<{
        node_id: string;
        recipe_id: string;
        kind?: string | null;
        duration_ticks?: number | null;
        x: number;
        y: number;
    }>;
    edges: Array<{
        edge_id: string;
        source_node_id: string;
        target_node_id: string;
        item_id: string;
        amount: number;
    }>;
};

function getSlotItem(
    node: CanvasNodeRecord,
    slotType: SlotType,
    index: number,
): RecipeItem | undefined {
    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index];
}

function resolveConnectionEnds(connection: RecipeConnection) {
    if (connection.from.slotType === 'output' && connection.to.slotType === 'input') {
        return { producer: connection.from, consumer: connection.to };
    }
    if (connection.from.slotType === 'input' && connection.to.slotType === 'output') {
        return { producer: connection.to, consumer: connection.from };
    }
    return null;
}

export function canvasToBackendGraph(
    nodes: CanvasNodeRecord[],
    connections: RecipeConnection[],
): BackendCanvasGraph {
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const itemNodes: BackendCanvasGraph['item_nodes'] = [];
    const recipeNodes: BackendCanvasGraph['recipe_nodes'] = [];
    const edges: BackendCanvasGraph['edges'] = [];

    const ensureItemNode = (
        nodeId: string,
        itemId: string,
        amount: number,
        x: number,
        y: number,
    ) => {
        if (itemNodes.some((node) => node.node_id === nodeId)) {
            return;
        }
        itemNodes.push({
            node_id: nodeId,
            item_id: itemId,
            amount,
            x,
            y,
        });
    };

    for (const node of nodes) {
        if (node.kind === 'recipe') {
            if (!node.recipeId) {
                throw new CanvasConversionError(`Recipe node ${node.id} is missing recipeId`);
            }
            recipeNodes.push({
                node_id: node.id,
                recipe_id: node.recipeId,
                kind: null,
                duration_ticks: node.durationTicks ?? null,
                x: node.x,
                y: node.y,
            });
            continue;
        }

        if (node.kind === 'chest' || node.kind === 'outpost') {
            recipeNodes.push({
                node_id: node.id,
                recipe_id: node.recipeId ?? `${node.kind}:${node.id}`,
                kind: node.kind,
                duration_ticks: null,
                x: node.x,
                y: node.y,
            });
        }
    }

    for (const connection of connections) {
        const ends = resolveConnectionEnds(connection);
        if (!ends) {
            continue;
        }

        const producerNode = nodeById.get(ends.producer.nodeId);
        const consumerNode = nodeById.get(ends.consumer.nodeId);
        if (!producerNode || !consumerNode) {
            continue;
        }

        const outputItem = getSlotItem(producerNode, ends.producer.slotType, ends.producer.itemIndex);
        const inputItem = getSlotItem(consumerNode, ends.consumer.slotType, ends.consumer.itemIndex);
        const itemId = outputItem?.item_id ?? inputItem?.item_id;
        if (!itemId) {
            throw new CanvasConversionError(`Невозможно рассчитать: нет item_id для связи ${connection.id}`);
        }

        const amount = outputItem?.amount ?? inputItem?.amount ?? 1;
        const itemNodeId = `item-${connection.id}`;
        ensureItemNode(
            itemNodeId,
            itemId,
            amount,
            (producerNode.x + consumerNode.x) / 2,
            (producerNode.y + consumerNode.y) / 2,
        );

        if (producerNode.kind === 'recipe') {
            edges.push({
                edge_id: `${connection.id}-out`,
                source_node_id: ends.producer.nodeId,
                target_node_id: itemNodeId,
                item_id: itemId,
                amount,
            });
        }

        if (consumerNode.kind === 'recipe') {
            edges.push({
                edge_id: `${connection.id}-in`,
                source_node_id: itemNodeId,
                target_node_id: ends.consumer.nodeId,
                item_id: itemId,
                amount,
            });
        }
    }

    for (const node of nodes) {
        if (node.kind !== 'recipe') {
            continue;
        }

        node.inputs.forEach((input, index) => {
            if (!input.item_id || !input.name) {
                return;
            }
            if (isSlotConnected(node.id, 'input', index, connections)) {
                return;
            }

            const itemNodeId = `raw-${node.id}-in-${index}`;
            ensureItemNode(itemNodeId, input.item_id, input.amount, node.x - 48, node.y);
            edges.push({
                edge_id: `raw-edge-${node.id}-in-${index}`,
                source_node_id: itemNodeId,
                target_node_id: node.id,
                item_id: input.item_id,
                amount: input.amount,
            });
        });
    }

    return { item_nodes: itemNodes, recipe_nodes: recipeNodes, edges };
}
