import type { RecipeConnection, RecipeItem, NodeKind } from '../types/recipe';
import type { FlowRateUnit, ProductionTarget } from '../types/production';
import type { CanvasTransform } from './canvasCoords';

export const CANVAS_FILE_VERSION = 2 as const;
export const LEGACY_CANVAS_FILE_VERSION = 1 as const;
export const DEFAULT_DURATION_TICKS = 100;
export const TICKS_PER_SECOND = 20;

export interface CanvasNodeRecord {
    id: string;
    kind: NodeKind;
    recipeId?: string;
    x: number;
    y: number;
    machineName: string;
    inputs: RecipeItem[];
    outputs: RecipeItem[];
    durationTicks?: number;
}

export interface CanvasDocumentMeta {
    name?: string;
    updatedAt?: string;
    defaultDurationTicks?: number;
    flowRateUnit?: FlowRateUnit;
    productionTarget?: ProductionTarget;
}

export interface CanvasDocument {
    version: typeof CANVAS_FILE_VERSION | typeof LEGACY_CANVAS_FILE_VERSION;
    minecraftVersion?: string;
    profileId?: string;
    meta?: CanvasDocumentMeta;
    /** Pan/zoom при открытии; позиции нод всегда в координатах холста. */
    viewport?: CanvasTransform;
    nodes: CanvasNodeRecord[];
    connections: RecipeConnection[];
}
