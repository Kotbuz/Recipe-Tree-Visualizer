import { useCallback, useState } from 'react';

export type DependencyDownloadResult = {
    dependency: string;
    status: string;
    jar_name?: string | null;
    source?: string | null;
    manual_url?: string | null;
    error?: string | null;
};

export type ModDependencyDownloadResponse = {
    version: string;
    requested: string[];
    results: DependencyDownloadResult[];
    all_resolved: boolean;
    export_triggered: boolean;
    export_recipe_count?: number | null;
    export_error?: string | null;
};

export function useModDependencyDownload(
    version: string,
    onComplete?: () => void | Promise<void>,
) {
    const [downloading, setDownloading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastResult, setLastResult] = useState<ModDependencyDownloadResponse | null>(null);

    const download = useCallback(async () => {
        if (!version) {
            return null;
        }

        setDownloading(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/download-missing-mod-dependencies`,
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
            const data = (await response.json()) as ModDependencyDownloadResponse;
            setLastResult(data);
            if (onComplete) {
                await onComplete();
            }
            return data;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Не удалось скачать зависимости';
            setError(message);
            return null;
        } finally {
            setDownloading(false);
        }
    }, [version, onComplete]);

    const clearResult = useCallback(() => {
        setLastResult(null);
        setError(null);
    }, []);

    return { download, downloading, error, lastResult, clearResult };
}
