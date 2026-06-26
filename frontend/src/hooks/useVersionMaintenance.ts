import { useCallback, useState } from 'react';
import type { RecipeExportStatus } from './useRecipeExportStatus';

export type ReloadModsResponse = {
    version: string;
    mod_count: number;
    export_status: RecipeExportStatus;
    export_recipe_count?: number | null;
    export_error?: string | null;
};

export type ClearRecipeExportResponse = {
    version: string;
    deleted_recipe_files: number;
    ore_dict_removed: boolean;
};

export function useVersionMaintenance(version: string) {
    const [reloading, setReloading] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastReload, setLastReload] = useState<ReloadModsResponse | null>(null);
    const [lastClear, setLastClear] = useState<ClearRecipeExportResponse | null>(null);

    const reloadMods = useCallback(async (): Promise<ReloadModsResponse> => {
        setReloading(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/reload-mods`,
                { method: 'POST' },
            );
            if (!response.ok) {
                let detail = `HTTP ${response.status}`;
                try {
                    const body = (await response.json()) as { detail?: string };
                    if (body.detail) {
                        detail = body.detail;
                    }
                } catch {
                    // ignore
                }
                throw new Error(detail);
            }
            const data = (await response.json()) as ReloadModsResponse;
            setLastReload(data);
            return data;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Не удалось перезагрузить моды';
            setError(message);
            throw err;
        } finally {
            setReloading(false);
        }
    }, [version]);

    const clearRecipeExport = useCallback(async (): Promise<ClearRecipeExportResponse> => {
        setClearing(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/clear-recipe-export`,
                { method: 'POST' },
            );
            if (!response.ok) {
                let detail = `HTTP ${response.status}`;
                try {
                    const body = (await response.json()) as { detail?: string };
                    if (body.detail) {
                        detail = body.detail;
                    }
                } catch {
                    // ignore
                }
                throw new Error(detail);
            }
            const data = (await response.json()) as ClearRecipeExportResponse;
            setLastClear(data);
            return data;
        } catch (err) {
            const message =
                err instanceof Error ? err.message : 'Не удалось очистить кэш рецептов';
            setError(message);
            throw err;
        } finally {
            setClearing(false);
        }
    }, [version]);

    return {
        reloading,
        clearing,
        error,
        lastReload,
        lastClear,
        reloadMods,
        clearRecipeExport,
    };
}
