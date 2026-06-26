export type ForgeInstallStatus = {
    minecraft_version: string;
    forge_build: string;
    installed: boolean;
    running: boolean;
    phase: string;
    message: string;
    progress: number;
    error: string | null;
};

const POLL_INTERVAL_MS = 1000;

async function fetchForgeStatus(
    version: string,
    forgeBuild: string,
): Promise<ForgeInstallStatus> {
    const params = new URLSearchParams({ forge_build: forgeBuild });
    const response = await fetch(
        `/versions/${encodeURIComponent(version)}/forge/install-status?${params.toString()}`,
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
    return (await response.json()) as ForgeInstallStatus;
}

export async function prepareForgeInstall(
    version: string,
    forgeBuild: string,
    onProgress?: (status: ForgeInstallStatus) => void,
): Promise<ForgeInstallStatus> {
    const initial = await fetchForgeStatus(version, forgeBuild);
    if (initial.installed) {
        onProgress?.(initial);
        return initial;
    }

    const response = await fetch(
        `/versions/${encodeURIComponent(version)}/forge/prepare`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ forge_build: forgeBuild }),
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

    let status = (await response.json()) as ForgeInstallStatus;
    onProgress?.(status);

    while (status.running || (!status.installed && status.phase !== 'error')) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        status = await fetchForgeStatus(version, forgeBuild);
        onProgress?.(status);
        if (status.installed) {
            return status;
        }
        if (status.error) {
            throw new Error(status.error);
        }
        if (!status.running && !status.installed) {
            throw new Error(status.message || 'Установка Forge прервана');
        }
    }

    if (status.error) {
        throw new Error(status.error);
    }
    return status;
}
