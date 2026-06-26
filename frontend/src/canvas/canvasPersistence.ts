import {
    CANVAS_FILE_VERSION,
    DEFAULT_DURATION_TICKS,
    LEGACY_CANVAS_FILE_VERSION,
    type CanvasDocument,
    type CanvasNodeRecord,
} from './canvasSchema';
import type { CanvasTransform } from './canvasCoords';
import type { RecipeConnection } from '../types/recipe';
import type { FlowRateUnit, ProductionTarget } from '../types/production';

export function createCanvasDocument(params: {
    nodes: CanvasNodeRecord[];
    connections: RecipeConnection[];
    viewport?: CanvasTransform;
    name?: string;
    minecraftVersion?: string;
    profileId?: string;
    defaultDurationTicks?: number;
    flowRateUnit?: FlowRateUnit;
    productionTarget?: ProductionTarget | null;
}): CanvasDocument {
    return {
        version: CANVAS_FILE_VERSION,
        minecraftVersion: params.minecraftVersion,
        profileId: params.profileId,
        meta: {
            name: params.name,
            updatedAt: new Date().toISOString(),
            defaultDurationTicks: params.defaultDurationTicks ?? DEFAULT_DURATION_TICKS,
            flowRateUnit: params.flowRateUnit,
            productionTarget: params.productionTarget ?? undefined,
        },
        viewport: params.viewport,
        nodes: params.nodes,
        connections: params.connections,
    };
}

function migrateV1Document(data: {
    version: 1;
    meta?: CanvasDocument['meta'];
    viewport?: CanvasTransform;
    nodes: CanvasNodeRecord[];
    connections: RecipeConnection[];
}): CanvasDocument {
    return {
        version: CANVAS_FILE_VERSION,
        meta: {
            ...data.meta,
            defaultDurationTicks: data.meta?.defaultDurationTicks ?? DEFAULT_DURATION_TICKS,
        },
        viewport: data.viewport,
        nodes: data.nodes.map((node) => {
            if (node.kind !== 'recipe' || node.durationTicks !== undefined) {
                return node;
            }
            return { ...node, durationTicks: DEFAULT_DURATION_TICKS };
        }),
        connections: data.connections,
    };
}

export function parseCanvasDocument(raw: string): CanvasDocument {
    const data = JSON.parse(raw) as {
        version: number;
        meta?: CanvasDocument['meta'];
        viewport?: CanvasTransform;
        nodes: CanvasNodeRecord[];
        connections: RecipeConnection[];
    };

    if (data.version === 1) {
        return migrateV1Document(data as Parameters<typeof migrateV1Document>[0]);
    }

    if (
        data.version !== CANVAS_FILE_VERSION &&
        data.version !== LEGACY_CANVAS_FILE_VERSION
    ) {
        throw new Error(`Неподдерживаемая версия файла: ${data.version}`);
    }

    if (!Array.isArray(data.nodes) || !Array.isArray(data.connections)) {
        throw new Error('Некорректный формат файла холста');
    }

    return data as CanvasDocument;
}

export function serializeCanvasDocument(document: CanvasDocument): string {
    return JSON.stringify(document, null, 2);
}

export function downloadCanvasDocument(document: CanvasDocument, filename = 'recipe-tree.json') {
    const blob = new Blob([serializeCanvasDocument(document)], {
        type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

export function pickCanvasDocumentFile(): Promise<CanvasDocument> {
    return new Promise((resolve, reject) => {
        const input = window.document.createElement('input');
        input.type = 'file';
        input.accept = 'application/json,.json';

        input.onchange = async () => {
            const file = input.files?.[0];
            if (!file) {
                reject(new Error('Файл не выбран'));
                return;
            }

            try {
                const text = await file.text();
                resolve(parseCanvasDocument(text));
            } catch (error) {
                reject(error);
            }
        };

        input.click();
    });
}
