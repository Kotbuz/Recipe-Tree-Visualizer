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

export function useProfileIntegrity(version: string, profileId?: string) {
    const [checking, setChecking] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [report, setReport] = useState<ProfileIntegrityReport | null>(null);

    const checkIntegrity = useCallback(async (): Promise<ProfileIntegrityReport | null> => {
        if (!version || !profileId || profileId === 'default') {
            setReport(null);
            return null;
        }

        setChecking(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/integrity`,
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
    }, [version, profileId]);

    const syncFromSource = useCallback(async (): Promise<ProfileSyncResult | null> => {
        if (!version || !profileId || profileId === 'default') {
            return null;
        }

        setSyncing(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(version)}/profiles/${encodeURIComponent(profileId)}/sync`,
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
            const data = (await response.json()) as ProfileSyncResult;
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
    }, [version, profileId]);

    const clearReport = useCallback(() => {
        setReport(null);
        setError(null);
    }, []);

    return {
        checking,
        syncing,
        error,
        report,
        checkIntegrity,
        syncFromSource,
        clearReport,
    };
}
