import type { RecipeConnection, SlotType } from '../types/recipe';

export function isSlotConnected(
    nodeId: string,
    slotType: SlotType,
    itemIndex: number,
    connections: RecipeConnection[],
): boolean {
    return connections.some(
        (connection) =>
            (connection.from.nodeId === nodeId &&
                connection.from.slotType === slotType &&
                connection.from.itemIndex === itemIndex) ||
            (connection.to.nodeId === nodeId &&
                connection.to.slotType === slotType &&
                connection.to.itemIndex === itemIndex),
    );
}
