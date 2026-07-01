import type { CanvasNodeRecord } from './canvasSchema';
import type { RecipeConnection, SlotType } from '../types/recipe';
import type { ProductionPlan } from '../types/production';

function getSlotItemId(node: CanvasNodeRecord, slotType: SlotType, index: number): string | undefined {
    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index]?.item_id;
}

function resolveProducerSlot(connection: RecipeConnection) {
    if (connection.from.slotType === 'output' && connection.to.slotType === 'input') {
        return connection.from;
    }
    if (connection.from.slotType === 'input' && connection.to.slotType === 'output') {
        return connection.to;
    }
    return null;
}

function backendNodeId(nodeId: string): string {
    return nodeId;
}

function findStageRate(
    plan: ProductionPlan,
    recipeNodeId: string,
    itemId: string,
    direction: 'output' | 'input',
): number | undefined {
    const stage = plan.stages.find((entry) => entry.recipe_node_id === recipeNodeId);
    if (!stage) {
        return undefined;
    }

    const rates = direction === 'output' ? stage.output_rates : stage.input_rates;
    if (rates[itemId] !== undefined) {
        return rates[itemId];
    }

    const tagMatch = Object.entries(rates).find(([key]) => key.startsWith('tag:') && itemId.includes(':'));
    return tagMatch?.[1];
}

export function buildConnectionFlowRates(
    nodes: CanvasNodeRecord[],
    connections: RecipeConnection[],
    plan: ProductionPlan,
): Map<string, number> {
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const rates = new Map<string, number>();

    for (const connection of connections) {
        const producerSlot = resolveProducerSlot(connection);
        if (!producerSlot) {
            continue;
        }

        const producerNode = nodeById.get(producerSlot.nodeId);
        if (!producerNode?.recipeId) {
            continue;
        }

        const itemId = getSlotItemId(producerNode, producerSlot.slotType, producerSlot.itemIndex);
        if (!itemId) {
            continue;
        }

        const rate = findStageRate(
            plan,
            backendNodeId(producerSlot.nodeId),
            itemId,
            'output',
        );
        if (rate !== undefined) {
            rates.set(connection.id, rate);
            continue;
        }

        const consumerSlot =
            connection.from.nodeId === producerSlot.nodeId ? connection.to : connection.from;
        const consumerNode = nodeById.get(consumerSlot.nodeId);
        if (!consumerNode?.recipeId) {
            continue;
        }

        const consumerItemId = getSlotItemId(consumerNode, consumerSlot.slotType, consumerSlot.itemIndex);
        if (!consumerItemId) {
            continue;
        }

        const inputRate = findStageRate(
            plan,
            backendNodeId(consumerSlot.nodeId),
            consumerItemId,
            'input',
        );
        if (inputRate !== undefined) {
            rates.set(connection.id, inputRate);
        }
    }

    return rates;
}

export function buildMachineCountByNodeId(
    nodes: CanvasNodeRecord[],
    plan: ProductionPlan | null,
): Map<string, { machineCount: number; limitApplied: boolean }> {
    const result = new Map<string, { machineCount: number; limitApplied: boolean }>();
    if (!plan) {
        return result;
    }
    for (const node of nodes) {
        if (node.kind !== 'recipe') {
            continue;
        }
        const stage = plan.stages.find((entry) => entry.recipe_node_id === backendNodeId(node.id));
        if (!stage) {
            continue;
        }
        result.set(node.id, {
            machineCount: stage.machine_count,
            limitApplied: stage.machine_limit_applied ?? false,
        });
    }
    return result;
}
