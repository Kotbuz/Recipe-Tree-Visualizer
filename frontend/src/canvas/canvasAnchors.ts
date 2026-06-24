import type { SlotType } from '../types/recipe';
import type { CanvasPoint } from './canvasCoords';

export type ConnectionSide = 'left' | 'right';

export interface CanvasAnchorPoint extends CanvasPoint {
    side: ConnectionSide;
}

export function slotConnectionSide(slotType: SlotType): ConnectionSide {
    return slotType === 'input' ? 'left' : 'right';
}

const tangentLength = (x1: number, x2: number) => Math.max(Math.abs(x2 - x1) * 0.45, 48);

/** Кривая Безье в координатах холста (для SVG внутри transform-слоя). */
export function buildCanvasBezierPath(from: CanvasAnchorPoint, to: CanvasAnchorPoint): string {
    const t = tangentLength(from.x, to.x);
    const cp1x = from.side === 'left' ? from.x - t : from.x + t;
    const cp2x = to.side === 'left' ? to.x - t : to.x + t;
    return `M ${from.x} ${from.y} C ${cp1x} ${from.y}, ${cp2x} ${to.y}, ${to.x} ${to.y}`;
}

/** Кривая в координатах viewport-local (для screen overlay без transform). */
export function buildViewportBezierPath(from: CanvasAnchorPoint, to: CanvasAnchorPoint): string {
    return buildCanvasBezierPath(from, to);
}

/**
 * Якорь слота в координатах холста.
 * node.x/y — центр ноды; DOM используется только для смещения слота относительно центра.
 */
export function getSlotAnchorCanvas(params: {
    nodeX: number;
    nodeY: number;
    slotType: SlotType;
    itemElement: HTMLElement;
    scale: number;
}): CanvasPoint | null {
    const nodeElement = params.itemElement.closest('.recipe-node') as HTMLElement | null;
    if (!nodeElement) return null;

    const nodeRect = nodeElement.getBoundingClientRect();
    const itemRect = params.itemElement.getBoundingClientRect();

    const anchorScreenX = params.slotType === 'input' ? itemRect.left : itemRect.right;
    const anchorScreenY = itemRect.top + itemRect.height / 2;
    const nodeCenterScreenX = nodeRect.left + nodeRect.width / 2;
    const nodeCenterScreenY = nodeRect.top + nodeRect.height / 2;

    return {
        x: params.nodeX + (anchorScreenX - nodeCenterScreenX) / params.scale,
        y: params.nodeY + (anchorScreenY - nodeCenterScreenY) / params.scale,
    };
}
