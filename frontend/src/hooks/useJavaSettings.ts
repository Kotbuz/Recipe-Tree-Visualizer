import { useCallback, useEffect, useState } from 'react';

export type JavaRuntimeInfo = {
    major: number;
    home: string;
    java_executable: string;
    label: string;
    source: string;
};

export type JavaSettings = {
    runtimes: JavaRuntimeInfo[];
    selected: Record<string, string>;
};

async function parseError(response: Response): Promise<string> {
    let detail = `HTTP ${response.status}`;
    try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) {
            detail = body.detail;
        }
    } catch {
        // ignore
    }
    return detail;
}

export function useJavaSettings() {
    const [settings, setSettings] = useState<JavaSettings | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [picking, setPicking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/settings/java');
            if (!response.ok) {
                throw new Error(await parseError(response));
            }
            setSettings((await response.json()) as JavaSettings);
        } catch (refreshError) {
            const message =
                refreshError instanceof Error
                    ? refreshError.message
                    : 'Не удалось загрузить настройки Java';
            setError(message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const setJavaHome = useCallback(async (major: number, home: string) => {
        setSaving(true);
        setError(null);
        try {
            const response = await fetch(`/settings/java/${major}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ major, home }),
            });
            if (!response.ok) {
                throw new Error(await parseError(response));
            }
            await refresh();
        } catch (saveError) {
            const message =
                saveError instanceof Error ? saveError.message : 'Не удалось сохранить Java';
            setError(message);
            throw saveError;
        } finally {
            setSaving(false);
        }
    }, [refresh]);

    const pickJava = useCallback(async (): Promise<{ home: string; major: number } | null> => {
        setPicking(true);
        setError(null);
        try {
            const response = await fetch('/settings/java/pick', { method: 'POST' });
            if (!response.ok) {
                throw new Error(await parseError(response));
            }
            const data = (await response.json()) as {
                home: string | null;
                cancelled?: boolean;
                major: number | null;
            };
            if (data.cancelled || !data.home || data.major == null) {
                return null;
            }
            await setJavaHome(data.major, data.home);
            return { home: data.home, major: data.major };
        } catch (pickError) {
            const message =
                pickError instanceof Error ? pickError.message : 'Не удалось выбрать Java';
            setError(message);
            throw pickError;
        } finally {
            setPicking(false);
        }
    }, [setJavaHome]);

    return {
        settings,
        loading,
        saving,
        picking,
        error,
        refresh,
        setJavaHome,
        pickJava,
        clearError: () => setError(null),
    };
}
