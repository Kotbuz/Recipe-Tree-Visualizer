import { useCallback, useEffect, useState } from 'react';

export type VersionCatalogEntry = {
    version: string;
    installed: boolean;
};

type VersionCatalogResponse = {
    releases: VersionCatalogEntry[];
};

type VersionInstallResponse = {
    version: string;
    client_jar_path: string;
    icons_rendered: number;
    icon_errors: string[];
};

export function useVersionCatalog() {
    const [catalog, setCatalog] = useState<VersionCatalogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [installingVersion, setInstallingVersion] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/versions/catalog');
            if (!response.ok) {
                throw new Error(`Не удалось загрузить каталог версий (${response.status})`);
            }
            const data = (await response.json()) as VersionCatalogResponse;
            setCatalog(data.releases ?? []);
        } catch (loadError) {
            const message =
                loadError instanceof Error ? loadError.message : 'Ошибка загрузки каталога';
            setError(message);
            setCatalog([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const installVersion = useCallback(
        async (version: string) => {
            setInstallingVersion(version);
            setError(null);
            try {
                const response = await fetch(`/versions/${encodeURIComponent(version)}/install`, {
                    method: 'POST',
                });
                if (!response.ok) {
                    let detail = `Ошибка установки (${response.status})`;
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

                const data = (await response.json()) as VersionInstallResponse;
                await refresh();
                return data;
            } catch (installError) {
                const message =
                    installError instanceof Error
                        ? installError.message
                        : 'Ошибка установки версии';
                setError(message);
                throw installError;
            } finally {
                setInstallingVersion(null);
            }
        },
        [refresh],
    );

    return {
        catalog,
        loading,
        installingVersion,
        error,
        refresh,
        installVersion,
    };
}
