import { useCallback, useEffect, useState } from 'react';

export type ProfileSummary = {
    profile_id: string;
    name: string;
    source: string;
    created_at: string;
    mod_count: number;
    active: boolean;
    loader?: string | null;
    forge_version?: string | null;
};

type ProfileListResponse = {
    version: string;
    active_profile_id: string;
    profiles: ProfileSummary[];
};

type ImportModpackResponse = {
    version: string;
    profile: ProfileSummary;
    jars_imported: number;
    config_files_imported: number;
    script_files_imported: number;
};

export function useProfiles(gameVersion: string) {
    const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
    const [activeProfileId, setActiveProfileId] = useState('default');
    const [loading, setLoading] = useState(true);
    const [importing, setImporting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [deletingProfileId, setDeletingProfileId] = useState<string | null>(null);

    const refresh = useCallback(async (versionOverride?: string) => {
        const resolvedVersion = versionOverride ?? gameVersion;
        if (!resolvedVersion) {
            setProfiles([]);
            setActiveProfileId('default');
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(resolvedVersion)}/profiles`,
            );
            if (!response.ok) {
                throw new Error(`Не удалось загрузить профили (${response.status})`);
            }
            const data = (await response.json()) as ProfileListResponse;
            setProfiles(data.profiles ?? []);
            setActiveProfileId(data.active_profile_id || 'default');
        } catch (loadError) {
            const message =
                loadError instanceof Error ? loadError.message : 'Ошибка загрузки профилей';
            setError(message);
            setProfiles([]);
        } finally {
            setLoading(false);
        }
    }, [gameVersion]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const activateProfile = useCallback(
        async (profileId: string) => {
            if (!gameVersion || !profileId) {
                return;
            }
            setError(null);
            const response = await fetch(
                `/versions/${encodeURIComponent(gameVersion)}/profiles/${encodeURIComponent(profileId)}/activate`,
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
            await refresh();
        },
        [gameVersion, refresh],
    );

    const importModpackZip = useCallback(
        async (file: File, options?: { name?: string; targetVersion?: string }) => {
            const targetVersion = options?.targetVersion ?? gameVersion;
            if (!targetVersion) {
                return null;
            }
            setImporting(true);
            setError(null);
            try {
                const formData = new FormData();
                formData.append('file', file);
                const url = new URL(
                    `/versions/${encodeURIComponent(targetVersion)}/profiles/import-modpack`,
                    window.location.origin,
                );
                const name = options?.name;
                if (name) {
                    url.searchParams.set('name', name);
                }
                const response = await fetch(url, { method: 'POST', body: formData });
                if (!response.ok) {
                    let detail = `Ошибка импорта (${response.status})`;
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
                const data = (await response.json()) as ImportModpackResponse;
                setActiveProfileId(data.profile.profile_id);
                await refresh(targetVersion);
                return data;
            } catch (importError) {
                const message =
                    importError instanceof Error ? importError.message : 'Ошибка импорта модпака';
                setError(message);
                throw importError;
            } finally {
                setImporting(false);
            }
        },
        [gameVersion, refresh],
    );

    const importFromPath = useCallback(
        async (path: string, options?: { name?: string; targetVersion?: string }) => {
            const targetVersion = options?.targetVersion ?? gameVersion;
            if (!targetVersion || !path.trim()) {
                return null;
            }
            setImporting(true);
            setError(null);
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(targetVersion)}/profiles/import-path`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: path.trim(), name: options?.name }),
                    },
                );
                if (!response.ok) {
                    let detail = `Ошибка импорта (${response.status})`;
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
                const data = (await response.json()) as ImportModpackResponse;
                setActiveProfileId(data.profile.profile_id);
                await refresh(targetVersion);
                return data;
            } catch (importError) {
                const message =
                    importError instanceof Error ? importError.message : 'Ошибка импорта папки';
                setError(message);
                throw importError;
            } finally {
                setImporting(false);
            }
        },
        [gameVersion, refresh],
    );

    const deleteProfile = useCallback(
        async (profileId: string) => {
            if (!gameVersion || !profileId || profileId === 'default') {
                return;
            }
            setDeletingProfileId(profileId);
            setError(null);
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(gameVersion)}/profiles/${encodeURIComponent(profileId)}`,
                    { method: 'DELETE' },
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
                const data = (await response.json()) as ProfileListResponse;
                setProfiles(data.profiles ?? []);
                setActiveProfileId(data.active_profile_id || 'default');
                await refresh();
            } catch (deleteError) {
                const message =
                    deleteError instanceof Error
                        ? deleteError.message
                        : 'Ошибка удаления профиля';
                setError(message);
                throw deleteError;
            } finally {
                setDeletingProfileId(null);
            }
        },
        [gameVersion, refresh],
    );

    const activeProfile =
        profiles.find((profile) => profile.profile_id === activeProfileId) ?? null;

    return {
        profiles,
        activeProfileId,
        activeProfile,
        loading,
        importing,
        deletingProfileId,
        error,
        refresh,
        activateProfile,
        deleteProfile,
        importModpackZip,
        importFromPath,
    };
}
