import { useCallback, useState } from 'react';

export type RecipeBakeStatus = {
    version: string;
    profile_id: string;
    has_snapshot: boolean;
    recipe_count: number;
    item_count: number;
    exported_at?: string | null;
    minecraft_version?: string | null;
    loader_version?: string | null;
    last_error?: string | null;
    export_running: boolean;
};

export type RecipeBakeResult = {
    version: string;
    profile_id: string;
    status: string;
    recipe_count: number;
    item_count: number;
    duration_seconds?: number | null;
    log_tail?: string | null;
    error?: string | null;
    kept_previous_snapshot: boolean;
    backend_log_path?: string | null;
    bake_log_path?: string | null;
};

async function readApiError(response: Response): Promise<string> {
    const detail = await response.text();
    const trimmed = detail.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
            const parsed = JSON.parse(trimmed) as { detail?: string };
            return parsed.detail ?? trimmed;
        } catch {
            return trimmed;
        }
    }
    if (trimmed.startsWith('<')) {
        return `HTTP ${response.status}: сервер вернул HTML вместо JSON (проверьте прокси nginx /api)`;
    }
    return trimmed || `HTTP ${response.status}`;
}

async function readApiJson<T>(response: Response): Promise<T> {
    const text = await response.text();
    const trimmed = text.trim();
    if (!trimmed) {
        throw new Error('Пустой ответ сервера');
    }
    if (trimmed.startsWith('<')) {
        throw new Error(
            'Сервер вернул HTML вместо JSON — запрос не дошёл до backend (часто nginx без прокси /api)',
        );
    }
    try {
        return JSON.parse(trimmed) as T;
    } catch {
        throw new Error('Ответ сервера не является JSON');
    }
}

export function useRecipeBake(version: string, profileId?: string) {
    const [baking, setBaking] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [status, setStatus] = useState<RecipeBakeStatus | null>(null);
    const [lastResult, setLastResult] = useState<RecipeBakeResult | null>(null);

    const refreshStatus = useCallback(async (): Promise<RecipeBakeStatus | null> => {
        if (!version || !profileId || profileId === 'default') {
            setStatus(null);
            return null;
        }
        setLoadingStatus(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/bake-recipes/status`,
            );
            if (!response.ok) {
                throw new Error(await readApiError(response));
            }
            const payload = await readApiJson<RecipeBakeStatus>(response);
            setStatus(payload);
            return payload;
        } catch (caught) {
            const message = caught instanceof Error ? caught.message : 'Не удалось загрузить статус снимка';
            setError(message);
            return null;
        } finally {
            setLoadingStatus(false);
        }
    }, [version, profileId]);

    const bakeRecipes = useCallback(
        async (options?: { force?: boolean; sourcePath?: string }): Promise<RecipeBakeResult | null> => {
            if (!version || !profileId || profileId === 'default') {
                return null;
            }
            setBaking(true);
            setError(null);
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/bake-recipes`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            force: options?.force ?? true,
                            source_path: options?.sourcePath?.trim() || undefined,
                        }),
                    },
                );
                if (!response.ok) {
                    throw new Error(await readApiError(response));
                }
                const payload = await readApiJson<RecipeBakeResult>(response);
                setLastResult(payload);
                if (payload.status !== 'ok' && payload.error) {
                    setError(payload.error);
                }
                await refreshStatus();
                return payload;
            } catch (caught) {
                const message = caught instanceof Error ? caught.message : 'Сборка рецептов не удалась';
                setError(message);
                return null;
            } finally {
                setBaking(false);
            }
        },
        [version, profileId, refreshStatus],
    );

    return {
        baking,
        loadingStatus,
        error,
        status,
        lastResult,
        refreshStatus,
        bakeRecipes,
    };
}
