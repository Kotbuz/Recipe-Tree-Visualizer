import { useCallback, useEffect, useState } from 'react';

export type RecipeStats = {
    version: string;
    profile_id: string;
    has_stats: boolean;
    recipe_count: number;
    item_count: number;
    source: 'snapshot' | 'catalog' | 'none';
};

/**
 * Статус `Nр · Mп` под профилем: vanilla — из каталога версии, модпак — из снимка.
 * Модпак без снимка → has_stats=false (статистику не показываем).
 */
export function useRecipeStats(version: string, profileId?: string) {
    const [stats, setStats] = useState<RecipeStats | null>(null);
    const [loading, setLoading] = useState(false);

    const refresh = useCallback(async (): Promise<RecipeStats | null> => {
        if (!version || !profileId) {
            setStats(null);
            return null;
        }
        setLoading(true);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/recipe-stats`,
            );
            if (!response.ok) {
                setStats(null);
                return null;
            }
            const payload = (await response.json()) as RecipeStats;
            setStats(payload);
            return payload;
        } catch {
            setStats(null);
            return null;
        } finally {
            setLoading(false);
        }
    }, [version, profileId]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return { stats, loading, refresh };
}
