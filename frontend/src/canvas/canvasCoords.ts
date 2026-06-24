import { CANVAS_CONFIG } from './canvasConfig';

export interface CanvasPoint {
    x: number;
    y: number;
}

export interface ScreenPoint {
    x: number;
    y: number;
}

/** Pan/zoom viewport: сдвиг и масштаб в пикселях viewport-элемента. */
export interface CanvasTransform {
    offsetX: number;
    offsetY: number;
    scale: number;
}

export interface CanvasViewportRect {
    left: number;
    top: number;
    width: number;
    height: number;
}

export interface CanvasCoordSystem {
    transform: CanvasTransform;
    rect: CanvasViewportRect | null;
    screenToCanvas: (clientX: number, clientY: number) => CanvasPoint | null;
    canvasToScreen: (point: CanvasPoint) => ScreenPoint | null;
    /** Координаты внутри viewport-элемента до CSS transform контента. */
    canvasToViewportLocal: (point: CanvasPoint) => CanvasPoint | null;
    viewportLocalFromScreen: (clientX: number, clientY: number) => CanvasPoint | null;
    clampCanvasPoint: (point: CanvasPoint) => CanvasPoint;
    snapCanvasPoint: (point: CanvasPoint) => CanvasPoint;
}

export const DEFAULT_CANVAS_TRANSFORM: CanvasTransform = {
    offsetX: 0,
    offsetY: 0,
    scale: 1,
};

export function toViewportRect(rect: DOMRect): CanvasViewportRect {
    return {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
    };
}

export function screenToCanvasPoint(
    clientX: number,
    clientY: number,
    rect: CanvasViewportRect,
    transform: CanvasTransform,
): CanvasPoint {
    return {
        x: (clientX - rect.left - transform.offsetX) / transform.scale,
        y: (clientY - rect.top - transform.offsetY) / transform.scale,
    };
}

export function canvasToScreenPoint(
    point: CanvasPoint,
    rect: CanvasViewportRect,
    transform: CanvasTransform,
): ScreenPoint {
    return {
        x: rect.left + transform.offsetX + point.x * transform.scale,
        y: rect.top + transform.offsetY + point.y * transform.scale,
    };
}

export function canvasToViewportLocalPoint(
    point: CanvasPoint,
    transform: CanvasTransform,
): CanvasPoint {
    return {
        x: transform.offsetX + point.x * transform.scale,
        y: transform.offsetY + point.y * transform.scale,
    };
}

export function viewportLocalFromScreenPoint(
    clientX: number,
    clientY: number,
    rect: CanvasViewportRect,
): CanvasPoint {
    return {
        x: clientX - rect.left,
        y: clientY - rect.top,
    };
}

export function clampCanvasPoint(point: CanvasPoint): CanvasPoint {
    const limit = CANVAS_CONFIG.virtual.halfExtent;
    return {
        x: Math.max(-limit, Math.min(limit, point.x)),
        y: Math.max(-limit, Math.min(limit, point.y)),
    };
}

export function snapCanvasPoint(point: CanvasPoint): CanvasPoint {
    if (!CANVAS_CONFIG.snap.enabled) {
        return point;
    }

    const grid = CANVAS_CONFIG.snap.gridSize;
    return {
        x: Math.round(point.x / grid) * grid,
        y: Math.round(point.y / grid) * grid,
    };
}

export function normalizeCanvasPoint(point: CanvasPoint): CanvasPoint {
    return snapCanvasPoint(clampCanvasPoint(point));
}

export function createCanvasCoordSystem(
    transform: CanvasTransform,
    rect: CanvasViewportRect | null,
): CanvasCoordSystem {
    const screenToCanvas = (clientX: number, clientY: number) => {
        if (!rect) return null;
        return screenToCanvasPoint(clientX, clientY, rect, transform);
    };

    const canvasToScreen = (point: CanvasPoint) => {
        if (!rect) return null;
        return canvasToScreenPoint(point, rect, transform);
    };

    const canvasToViewportLocal = (point: CanvasPoint) =>
        canvasToViewportLocalPoint(point, transform);

    const viewportLocalFromScreen = (clientX: number, clientY: number) => {
        if (!rect) return null;
        return viewportLocalFromScreenPoint(clientX, clientY, rect);
    };

    return {
        transform,
        rect,
        screenToCanvas,
        canvasToScreen,
        canvasToViewportLocal,
        viewportLocalFromScreen,
        clampCanvasPoint,
        snapCanvasPoint,
    };
}

export function applyWheelZoom(
    transform: CanvasTransform,
    pointerViewportX: number,
    pointerViewportY: number,
    deltaY: number,
): CanvasTransform {
    const factor = CANVAS_CONFIG.interaction.wheelZoomFactor;
    const delta = deltaY > 0 ? factor : 1 / factor;
    const { minScale, maxScale } = CANVAS_CONFIG.interaction;
    const newScale = Math.max(minScale, Math.min(maxScale, transform.scale * delta));
    const ratio = newScale / transform.scale;

    return {
        scale: newScale,
        offsetX: pointerViewportX - (pointerViewportX - transform.offsetX) * ratio,
        offsetY: pointerViewportY - (pointerViewportY - transform.offsetY) * ratio,
    };
}

export function buildTransformStyle(transform: CanvasTransform): string {
    return `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale})`;
}
