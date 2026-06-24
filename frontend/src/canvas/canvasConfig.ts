/** Единая конфигурация холста — меняйте здесь глобальные правила координат. */
export const CANVAS_CONFIG = {
    /** Логический размер холста: координаты нод в диапазоне ±halfExtent по осям. */
    virtual: {
        halfExtent: 10_000,
    },

    /** Ноды позиционируются по центру (CSS translate -50%, -50%). */
    nodeAnchor: 'center' as const,

    snap: {
        enabled: false,
        gridSize: 20,
    },

    interaction: {
        minScale: 0.5,
        maxScale: 3,
        wheelZoomFactor: 0.9,
        minItemDragDistance: 8,
        slotHitRadius: 28,
    },

    /**
     * SVG-слой связей: смещение, чтобы отрицательные координаты холста
     * оставались внутри viewBox без клиппинга.
     */
    layers: {
        connectionsSvgOffset: 10_000,
        connectionsSvgSize: 20_000,
    },
} as const;

export type CanvasNodeAnchor = (typeof CANVAS_CONFIG)['nodeAnchor'];
