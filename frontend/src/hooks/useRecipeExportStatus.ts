import { useCallback, useEffect, useState } from 'react';

export type ModDependencyIssue = {
    mod_id: string;
    jar_name: string;
    requires: string[];
};

export type RecipeExportStatus = {
    version: string;
    layout: string;
    exported_recipe_count: number;
    installed_mod_jars: string[];
    recipe_mod_ids: string[];
    mods_without_recipes: string[];
    missing_dependencies: ModDependencyIssue[];
    warnings: string[];
    log_errors?: string[];
};

export function useRecipeExportStatus(version: string) {
    const [status, setStatus] = useState<RecipeExportStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/recipe-export-status`,
            );
            if (!response.ok) {
                if (response.status === 404) {
                    setStatus(null);
                    return;
                }
                throw new Error(`HTTP ${response.status}`);
            }
            const data = (await response.json()) as RecipeExportStatus;
            setStatus(data);
            if (data.warnings.length > 0) {
                console.warn(
                    `[Recipe export ${version}]`,
                    data.warnings.join('\n'),
                    data,
                );
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load export status');
            setStatus(null);
        } finally {
            setLoading(false);
        }
    }, [version]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return { status, loading, error, refresh };
}
