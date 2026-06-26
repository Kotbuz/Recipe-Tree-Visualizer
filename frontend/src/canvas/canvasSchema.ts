import type { RecipeConnection, RecipeItem, NodeKind } from '../types/recipe';
import type { CanvasTransform } from './canvasCoords';

export const CANVAS_FILE_VERSION = 2 as const;
export const LEGACY_CANVAS_FILE_VERSION = 1 as const;

export interface CanvasNodeRecord {
    id: string;
    kind: NodeKind;
    recipeId?: string;
    x: number;
    y: number;
    machineName: string;
    inputs: RecipeItem[];
    outputs: RecipeItem[];
}

export interface CanvasDocument {
    version: typeof CANVAS_FILE_VERSION | typeof LEGACY_CANVAS_FILE_VERSION;
    minecraftVersion?: string;
    profileId?: string;
    meta?: {
        name?: string;
        updatedAt?: string;
    };
    /** Pan/zoom при открытии; позиции нод всегда в координатах холста. */
    viewport?: CanvasTransform;
    nodes: CanvasNodeRecord[];
    connections: RecipeConnection[];
}
