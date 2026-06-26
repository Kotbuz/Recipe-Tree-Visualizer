import {
    CANVAS_FILE_VERSION,
    LEGACY_CANVAS_FILE_VERSION,
    type CanvasDocument,
    type CanvasNodeRecord,
} from './canvasSchema';
import type { CanvasTransform } from './canvasCoords';
import type { RecipeConnection } from '../types/recipe';

export function createCanvasDocument(params: {
    nodes: CanvasNodeRecord[];
    connections: RecipeConnection[];
    viewport?: CanvasTransform;
    name?: string;
    minecraftVersion?: string;
    profileId?: string;
}): CanvasDocument {
    return {
        version: CANVAS_FILE_VERSION,
        minecraftVersion: params.minecraftVersion,
        profileId: params.profileId,
        meta: {
            name: params.name,
            updatedAt: new Date().toISOString(),
        },
        viewport: params.viewport,
        nodes: params.nodes,
        connections: params.connections,
    };
}

export function serializeCanvasDocument(document: CanvasDocument): string {
    return JSON.stringify(document, null, 2);
}

export function parseCanvasDocument(raw: string): CanvasDocument {
    const data = JSON.parse(raw) as CanvasDocument;

    if (
        data.version !== CANVAS_FILE_VERSION &&
        data.version !== LEGACY_CANVAS_FILE_VERSION
    ) {
        throw new Error(`Неподдерживаемая версия файла: ${data.version}`);
    }

    if (!Array.isArray(data.nodes) || !Array.isArray(data.connections)) {
        throw new Error('Некорректный формат файла холста');
    }

    return data;
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
