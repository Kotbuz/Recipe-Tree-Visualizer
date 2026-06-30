declare const __RTV_DESKTOP__: boolean | undefined;

const DESKTOP_API_BASE = 'http://127.0.0.1:8000';

const API_PREFIXES = [
    '/versions',
    '/mods',
    '/modpack',
    '/settings',
    '/graph',
    '/recipes',
    '/items',
    '/health',
];

export function isDesktopApp(): boolean {
    if (typeof __RTV_DESKTOP__ !== 'undefined' && __RTV_DESKTOP__) {
        return true;
    }
    if (typeof window === 'undefined') {
        return false;
    }
    return (
        '__TAURI_INTERNALS__' in window ||
        '__TAURI__' in window ||
        window.location.protocol === 'tauri:'
    );
}

export function getApiBase(): string {
    if (import.meta.env.DEV) {
        return '';
    }
    return isDesktopApp() ? DESKTOP_API_BASE : '';
}

function shouldProxyToApi(pathname: string): boolean {
    if (pathname.startsWith('/block/') || pathname.startsWith('/item/')) {
        return false;
    }
    if (pathname.startsWith('/assets/')) {
        return false;
    }
    return API_PREFIXES.some(
        (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
    );
}

export function resolveApiUrl(input: string | URL): string | URL {
    const base = getApiBase();
    if (!base) {
        return input;
    }

    if (typeof input === 'string') {
        if (input.startsWith('http://') || input.startsWith('https://')) {
            return input;
        }
        if (input.startsWith('/') && shouldProxyToApi(input)) {
            return `${base}${input}`;
        }
        return input;
    }

    if (shouldProxyToApi(input.pathname)) {
        return new URL(`${input.pathname}${input.search}${input.hash}`, base);
    }

    return input;
}

export function installDesktopFetchProxy(): void {
    if (!getApiBase()) {
        return;
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
        if (typeof input === 'string' || input instanceof URL) {
            return originalFetch(resolveApiUrl(input), init);
        }
        if (input instanceof Request) {
            const resolved = resolveApiUrl(input.url);
            if (resolved !== input.url) {
                return originalFetch(new Request(resolved, input), init);
            }
        }
        return originalFetch(input, init);
    };
}
