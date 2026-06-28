import { useCallback, useState } from 'react';

export type IntegrityIssue = {
    category: string;
    status: string;
    profile_count: number;
    source_count: number;
    missing_count: number;
    message: string;
};

export type ProfileIntegrityReport = {
    version: string;
    profile_id: string;
    source: string;
    source_path?: string | null;
    source_available: boolean;
    needs_source_path: boolean;
    healthy: boolean;
    can_sync: boolean;
    issues: IntegrityIssue[];
};

export type ProfileSyncResult = {
    version: string;
    profile_id: string;
    jars_synced: number;
    config_files_synced: number;
    script_files_synced: number;
    kubejs_server_scripts_synced: number;
    kubejs_data_files_synced: number;
    kubejs_asset_files_synced: number;
    integrity: ProfileIntegrityReport;
};

function resolveSourcePath(pathOverride: string | undefined, storedPath: string): string {
    const candidate = (pathOverride ?? storedPath).trim();
    return candidate;
}

export function useProfileIntegrity(version: string, profileId?: string) {
    const [checking, setChecking] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [report, setReport] = useState<ProfileIntegrityReport | null>(null);
    const [sourcePath, setSourcePath] = useState('');

    const checkIntegrity = useCallback(
        async (pathOverride?: string): Promise<ProfileIntegrityReport | null> => {
            if (!version || !profileId || profileId === 'default') {
                setReport(null);
                return null;
            }

            const activePath = resolveSourcePath(pathOverride, sourcePath);
            const query = activePath
                ? `?source_path=${encodeURIComponent(activePath)}`
                : '';

            setChecking(true);
            setError(null);
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/integrity${query}`,
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
                const data = (await response.json()) as ProfileIntegrityReport;
                if (data.source_path && !activePath) {
                    setSourcePath(data.source_path);
                }
                setReport(data);
                return data;
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : 'Не удалось проверить целостность профиля';
                setError(message);
                throw err;
            } finally {
                setChecking(false);
            }
        },
        [version, profileId, sourcePath],
    );

    const syncFromSource = useCallback(
        async (pathOverride?: string): Promise<ProfileSyncResult | null> => {
            if (!version || !profileId || profileId === 'default') {
                return null;
            }

            const activePath = resolveSourcePath(pathOverride, sourcePath);

            setSyncing(true);
            setError(null);
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/sync`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(activePath ? { path: activePath } : {}),
                    },
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
                const data = (await response.json()) as ProfileSyncResult;
                if (data.integrity.source_path) {
                    setSourcePath(data.integrity.source_path);
                }
                setReport(data.integrity);
                return data;
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : 'Не удалось подтянуть файлы из источника';
                setError(message);
                throw err;
            } finally {
                setSyncing(false);
            }
        },
        [version, profileId, sourcePath],
    );

    const clearReport = useCallback(() => {
        setReport(null);
        setError(null);
        setSourcePath('');
    }, []);

    return {
        checking,
        syncing,
        error,
        report,
        sourcePath,
        setSourcePath,
        checkIntegrity,
        syncFromSource,
        clearReport,
    };
}
