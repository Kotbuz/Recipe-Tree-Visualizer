import type { AssetRenderProgress } from '../hooks/useAssetRender';

export type OperationTone = 'default' | 'active' | 'success' | 'warn' | 'error' | 'muted';

export type OperationStatusLine = {
    key: string;
    label: string;
    text: string;
    tone: OperationTone;
    active?: boolean;
};

export function formatElapsed(seconds: number): string {
    if (seconds < 60) {
        return `${seconds} с`;
    }
    const minutes = Math.floor(seconds / 60);
    const restSeconds = seconds % 60;
    if (minutes < 60) {
        return restSeconds > 0 ? `${minutes} мин ${restSeconds} с` : `${minutes} мин`;
    }
    const hours = Math.floor(minutes / 60);
    const restMinutes = minutes % 60;
    return restMinutes > 0 ? `${hours} ч ${restMinutes} мин` : `${hours} ч`;
}

function isRendererUnavailableError(error: string | null | undefined): boolean {
    if (!error) {
        return false;
    }
    const lower = error.toLowerCase();
    return (
        lower.includes('renderer request failed') ||
        lower.includes('connection refused') ||
        lower.includes('connect error') ||
        lower.includes('could not connect') ||
        lower.includes('renderer недоступен')
    );
}

function formatAssetTask(
    label: string,
    key: string,
    task: { running: boolean; done: number; total: number; error?: string | null } | undefined,
    partial: boolean,
): OperationStatusLine {
    if (!task) {
        return { key, label, text: '—', tone: 'muted' };
    }
    if (task.running) {
        const text =
            task.total > 0 ? `${task.done} / ${task.total}` : 'запуск…';
        return { key, label, text, tone: 'active', active: true };
    }
    if (task.error) {
        if (label === 'Иконки' && isRendererUnavailableError(task.error)) {
            return {
                key,
                label,
                text: 'нужен renderer (Docker)',
                tone: 'warn',
            };
        }
        return { key, label, text: 'ошибка', tone: 'error' };
    }
    if (partial) {
        const text = task.total > 0 ? `частично (${task.done}/${task.total})` : 'частично';
        return { key, label, text, tone: 'warn' };
    }
    if (task.total > 0 && task.done >= task.total) {
        return { key, label, text: `готово (${task.total})`, tone: 'success' };
    }
    if (task.total > 0 && task.done > 0) {
        return { key, label, text: `${task.done} / ${task.total}`, tone: 'default' };
    }
    return { key, label, text: 'ожидание', tone: 'muted' };
}

export function buildOperationStatusLines(input: {
    exportActive: boolean;
    exportElapsedSec: number;
    exportDisabledReason: string | null;
    exportError: string | null;
    hasSnapshot: boolean;
    exportedAt: string | null;
    isDefaultProfile: boolean;
    assetProgress: AssetRenderProgress | null;
    iconsPartial: boolean;
    blocksPartial: boolean;
}): OperationStatusLine[] {
    let exportLine: OperationStatusLine;

    if (input.exportActive) {
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: `идёт · ${formatElapsed(input.exportElapsedSec)}`,
            tone: 'active',
            active: true,
        };
    } else if (input.exportError) {
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: 'ошибка',
            tone: 'error',
        };
    } else if (input.exportDisabledReason) {
        const short =
            input.exportDisabledReason.length > 42
                ? `${input.exportDisabledReason.slice(0, 41)}…`
                : input.exportDisabledReason;
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: short,
            tone: 'muted',
        };
    } else if (input.exportedAt) {
        const stamp = input.exportedAt.slice(0, 16).replace('T', ' ');
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: `готов · ${stamp}`,
            tone: 'success',
        };
    } else if (input.hasSnapshot) {
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: 'снимок есть',
            tone: 'success',
        };
    } else if (input.isDefaultProfile) {
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: 'не требуется',
            tone: 'muted',
        };
    } else {
        exportLine = {
            key: 'export',
            label: 'Экспорт',
            text: 'не выполнялся',
            tone: 'muted',
        };
    }

    return [
        exportLine,
        formatAssetTask('Иконки', 'icons', input.assetProgress?.icons, input.iconsPartial),
        formatAssetTask('Блоки', 'blocks', input.assetProgress?.blocks, input.blocksPartial),
    ];
}
