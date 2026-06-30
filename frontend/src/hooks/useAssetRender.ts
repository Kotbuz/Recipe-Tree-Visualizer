import { useCallback, useEffect, useRef, useState } from 'react';

export type AssetTaskProgress = {
    running: boolean;
    done: number;
    total: number;
    error?: string | null;
};

export type AssetRenderProgress = {
    version: string;
    profile_id: string;
    running: boolean;
    icons: AssetTaskProgress;
    blocks: AssetTaskProgress;
};

const ACTIVE_POLL_MS = 3000;
const IDLE_POLL_MS = 12000;

/**
 * Прогресс фонового рендера иконок и текстур блоков + запуск полного скана.
 * Опрос: 3 с пока идёт рендер, 12 с в простое (чтобы поймать рендер,
 * запущенный после экспорта или на старте приложения).
 */
export function useAssetRender(version: string, profileId?: string) {
    const [progress, setProgress] = useState<AssetRenderProgress | null>(null);
    const [starting, setStarting] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const refresh = useCallback(async (): Promise<AssetRenderProgress | null> => {
        if (!version || !profileId) {
            setProgress(null);
            return null;
        }
        try {
            const response = await fetch(
                `/api/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/asset-progress`,
            );
            if (!response.ok) {
                return null;
            }
            const payload = (await response.json()) as AssetRenderProgress;
            setProgress(payload);
            return payload;
        } catch {
            return null;
        }
    }, [version, profileId]);

    const startRender = useCallback(async (): Promise<{ started: boolean } | null> => {
        if (!version || !profileId) {
            return null;
        }
        setStarting(true);
        try {
            const response = await fetch(
                `/api/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/render-assets`,
                { method: 'POST' },
            );
            if (!response.ok) {
                let detail = await response.text();
                try {
                    detail = (JSON.parse(detail) as { detail?: string }).detail ?? detail;
                } catch {
                    // keep raw
                }
                throw new Error(detail || `HTTP ${response.status}`);
            }
            const payload = (await response.json()) as { started: boolean };
            await refresh();
            return payload;
        } finally {
            setStarting(false);
        }
    }, [version, profileId, refresh]);

    useEffect(() => {
        let cancelled = false;

        const tick = async () => {
            const result = await refresh();
            if (cancelled) {
                return;
            }
            const delay = result?.running ? ACTIVE_POLL_MS : IDLE_POLL_MS;
            timerRef.current = setTimeout(() => void tick(), delay);
        };

        void tick();
        return () => {
            cancelled = true;
            if (timerRef.current) {
                clearTimeout(timerRef.current);
            }
        };
    }, [refresh]);

    return { progress, starting, refresh, startRender };
}
