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

/**
 * Преобразует холст (включая вложенные холсты фабрик) в bipartite-граф backend.
 *
 * Фабрики с собственным subCanvas НЕ отправляются как терминальные recipe-ноды
 * (их синтетический recipe_id не прошёл бы валидацию backend). Вместо этого их
 * внутренние холсты рекурсивно «разворачиваются» в общий граф: в backend уходят
 * только реальные recipe-ноды (внешние и внутренние) + item-ноды. Стыковка границ
 * происходит естественно по item_id — движок сопоставляет производителя и
 * потребителя предмета независимо от уровня вложенности.
 */
export function canvasToBackendGraph(
    nodes: CanvasNodeRecord[],
    connections: RecipeConnection[],
): BackendCanvasGraph {
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

    const processCanvas = (
        levelNodes: CanvasNodeRecord[],
        levelConnections: RecipeConnection[],
        prefix: string,
    ) => {
        const ns = (id: string) => `${prefix}${id}`;
        const nodeById = new Map(levelNodes.map((node) => [node.id, node]));

        for (const node of levelNodes) {
            if (node.kind === 'recipe') {
                if (!node.recipeId) {
                    throw new CanvasConversionError(`Recipe node ${node.id} is missing recipeId`);
                }
                recipeNodes.push({
                    node_id: ns(node.id),
                    recipe_id: node.recipeId,
                    kind: null,
                    duration_ticks: node.durationTicks ?? null,
                    x: node.x,
                    y: node.y,
                });
                continue;
            }

            // Фабрика с содержимым — разворачиваем её холст вместо терминальной ноды.
            if (node.kind === 'outpost' && node.subCanvas) {
                processCanvas(
                    node.subCanvas.nodes,
                    node.subCanvas.connections,
                    `${ns(node.id)}::`,
                );
                continue;
            }

            // Сундук и пустая фабрика — терминальные проходные ноды (как раньше).
            if (node.kind === 'chest' || node.kind === 'outpost') {
                recipeNodes.push({
                    node_id: ns(node.id),
                    recipe_id: node.recipeId ?? `${node.kind}:${node.id}`,
                    kind: node.kind,
                    duration_ticks: null,
                    x: node.x,
                    y: node.y,
                });
            }

            // factory_in / factory_out — внутренняя «проводка», не эмитируем как recipe-ноды.
        }

        for (const connection of levelConnections) {
            const ends = resolveConnectionEnds(connection);
            if (!ends) {
                continue;
            }

            const producerNode = nodeById.get(ends.producer.nodeId);
            const consumerNode = nodeById.get(ends.consumer.nodeId);
            if (!producerNode || !consumerNode) {
                continue;
            }

            const outputItem = getSlotItem(
                producerNode,
                ends.producer.slotType,
                ends.producer.itemIndex,
            );
            const inputItem = getSlotItem(
                consumerNode,
                ends.consumer.slotType,
                ends.consumer.itemIndex,
            );
            const itemId = outputItem?.item_id ?? inputItem?.item_id;
            if (!itemId) {
                throw new CanvasConversionError(
                    `Невозможно рассчитать: нет item_id для связи ${connection.id}`,
                );
            }

            const amount = outputItem?.amount ?? inputItem?.amount ?? 1;
            const itemNodeId = ns(`item-${connection.id}`);
            ensureItemNode(
                itemNodeId,
                itemId,
                amount,
                (producerNode.x + consumerNode.x) / 2,
                (producerNode.y + consumerNode.y) / 2,
            );

            if (producerNode.kind === 'recipe') {
                edges.push({
                    edge_id: ns(`${connection.id}-out`),
                    source_node_id: ns(ends.producer.nodeId),
                    target_node_id: itemNodeId,
                    item_id: itemId,
                    amount,
                });
            }

            if (consumerNode.kind === 'recipe') {
                edges.push({
                    edge_id: ns(`${connection.id}-in`),
                    source_node_id: itemNodeId,
                    target_node_id: ns(ends.consumer.nodeId),
                    item_id: itemId,
                    amount,
                });
            }
        }

        for (const node of levelNodes) {
            if (node.kind !== 'recipe') {
                continue;
            }

            node.inputs.forEach((input, index) => {
                if (!input.item_id || !input.name) {
                    return;
                }
                if (isSlotConnected(node.id, 'input', index, levelConnections)) {
                    return;
                }

                const itemNodeId = ns(`raw-${node.id}-in-${index}`);
                ensureItemNode(itemNodeId, input.item_id, input.amount, node.x - 48, node.y);
                edges.push({
                    edge_id: ns(`raw-edge-${node.id}-in-${index}`),
                    source_node_id: itemNodeId,
                    target_node_id: ns(node.id),
                    item_id: input.item_id,
                    amount: input.amount,
                });
            });
        }
    };

    processCanvas(nodes, connections, '');

    return { item_nodes: itemNodes, recipe_nodes: recipeNodes, edges };
}
