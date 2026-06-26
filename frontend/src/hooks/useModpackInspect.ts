import { useCallback, useState } from 'react';

export type ModpackInspectResult = {
    minecraft_version: string;
    modpack_name: string | null;
    loader: string | null;
    forge_version: string | null;
    forge_installed: boolean | null;
    detection_source: string;
    version_installed: boolean;
    catalog_available: boolean;
};

async function parseInspectError(response: Response): Promise<string> {
    let detail = `HTTP ${response.status}`;
    try {
        const body = (await response.json()) as { detail?: string | { message?: string } };
        if (typeof body.detail === 'string') {
            return body.detail;
        }
        if (body.detail && typeof body.detail === 'object' && body.detail.message) {
            return body.detail.message;
        }
    } catch {
        // ignore
    }
    return detail;
}

export function useModpackInspect() {
    const [inspecting, setInspecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const inspectZip = useCallback(async (file: File): Promise<ModpackInspectResult> => {
        setInspecting(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/modpack/inspect', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                throw new Error(await parseInspectError(response));
            }
            return (await response.json()) as ModpackInspectResult;
        } catch (inspectError) {
            const message =
                inspectError instanceof Error
                    ? inspectError.message
                    : 'Не удалось проверить модпак';
            setError(message);
            throw inspectError;
        } finally {
            setInspecting(false);
        }
    }, []);

    const inspectPath = useCallback(async (path: string): Promise<ModpackInspectResult> => {
        setInspecting(true);
        setError(null);
        try {
            const response = await fetch('/modpack/inspect-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path.trim() }),
            });
            if (!response.ok) {
                throw new Error(await parseInspectError(response));
            }
            return (await response.json()) as ModpackInspectResult;
        } catch (inspectError) {
            const message =
                inspectError instanceof Error
                    ? inspectError.message
                    : 'Не удалось проверить папку инстанса';
            setError(message);
            throw inspectError;
        } finally {
            setInspecting(false);
        }
    }, []);

    const pickFolder = useCallback(async (): Promise<string | null> => {
        setInspecting(true);
        setError(null);
        try {
            return await pickInstanceFolder();
        } catch (pickError) {
            const message =
                pickError instanceof Error
                    ? pickError.message
                    : 'Не удалось выбрать папку';
            setError(message);
            throw pickError;
        } finally {
            setInspecting(false);
        }
    }, []);

    return {
        inspecting,
        error,
        inspectZip,
        inspectPath,
        pickFolder,
        clearError: () => setError(null),
    };
}

export async function pickInstanceFolder(): Promise<string | null> {
    const response = await fetch('/modpack/pick-folder', { method: 'POST' });
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
    const data = (await response.json()) as { path: string | null; cancelled?: boolean };
    if (data.cancelled || !data.path) {
        return null;
    }
    return data.path;
}
