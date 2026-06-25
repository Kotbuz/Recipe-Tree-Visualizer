import { useCallback, useEffect, useState } from 'react';

export type ModSummary = {
    mod_id: string;
    name: string;
    loader: string;
    minecraft_version?: string | null;
    minecraft_version_range?: string | null;
    jar_filename?: string | null;
    compatible?: boolean | null;
    item_count: number;
    recipe_count: number;
    machine_count: number;
    skipped_recipe_count: number;
};

type ModListResponse = {
    mods: ModSummary[];
};

export function useMods(gameVersion: string) {
    const [mods, setMods] = useState<ModSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const url = new URL('/mods', window.location.origin);
            url.searchParams.set('version', gameVersion);
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Не удалось загрузить список модов (${response.status})`);
            }
            const data = (await response.json()) as ModListResponse;
            setMods(data.mods ?? []);
        } catch (loadError) {
            const message =
                loadError instanceof Error ? loadError.message : 'Ошибка загрузки модов';
            setError(message);
            setMods([]);
        } finally {
            setLoading(false);
        }
    }, [gameVersion]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const upload = useCallback(
        async (files: FileList) => {
            if (files.length === 0) {
                return;
            }

            setUploading(true);
            setError(null);
            try {
                const formData = new FormData();
                for (const file of Array.from(files)) {
                    formData.append('files', file);
                }

                const response = await fetch('/mods/upload', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    let detail = `Ошибка загрузки (${response.status})`;
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
            } catch (uploadError) {
                const message =
                    uploadError instanceof Error ? uploadError.message : 'Ошибка загрузки модов';
                setError(message);
                throw uploadError;
            } finally {
                setUploading(false);
            }
        },
        [refresh],
    );

    const compatibleMods = mods.filter((mod) => mod.compatible !== false);

    return {
        mods,
        compatibleMods,
        loading,
        uploading,
        error,
        refresh,
        upload,
    };
}
