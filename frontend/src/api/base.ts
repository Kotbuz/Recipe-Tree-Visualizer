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
    '/profiles',
    '/health',
];

function isTauriWebviewOrigin(): boolean {
    if (typeof window === 'undefined') {
        return false;
    }
    const { hostname, protocol } = window.location;
    return (
        protocol === 'tauri:' ||
        hostname === 'tauri.localhost' ||
        hostname === 'asset.localhost' ||
        hostname.endsWith('.localhost')
    );
}

function isDockerSameOrigin(): boolean {
    if (typeof window === 'undefined') {
        return false;
    }
    const { hostname, port } = window.location;
    return (
        (hostname === 'localhost' || hostname === '127.0.0.1') &&
        (port === '' || port === '80')
    );
}

export function isDesktopApp(): boolean {
    if (typeof __RTV_DESKTOP__ !== 'undefined' && __RTV_DESKTOP__) {
        return true;
    }
    if (typeof window === 'undefined') {
        return false;
    }
    return (
        isTauriWebviewOrigin() ||
        '__TAURI_INTERNALS__' in window ||
        '__TAURI__' in window
    );
}

export function getApiBase(): string {
    if (import.meta.env.DEV) {
        return '';
    }
    if (typeof window === 'undefined') {
        return '';
    }
    if (isDockerSameOrigin()) {
        return '';
    }
    if (isDesktopApp() || isTauriWebviewOrigin()) {
        return DESKTOP_API_BASE;
    }
    return '';
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

function rewriteToApiBase(pathname: string, search: string, hash: string): string {
    const base = getApiBase();
    if (!base) {
        return `${pathname}${search}${hash}`;
    }
    return new URL(`${pathname}${search}${hash}`, base).toString();
}

function rewriteAbsoluteApiUrl(input: string): string | null {
    try {
        const parsed = new URL(input);
        if (!shouldProxyToApi(parsed.pathname)) {
            return null;
        }
        if (parsed.origin === DESKTOP_API_BASE) {
            return null;
        }
        return rewriteToApiBase(parsed.pathname, parsed.search, parsed.hash);
    } catch {
        return null;
    }
}

export function resolveApiUrl(input: string | URL): string | URL {
    const base = getApiBase();
    if (!base) {
        return input;
    }

    if (typeof input === 'string') {
        if (input.startsWith('http://') || input.startsWith('https://')) {
            return rewriteAbsoluteApiUrl(input) ?? input;
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

export function apiUrl(path: string): string {
    const resolved = resolveApiUrl(path);
    return typeof resolved === 'string' ? resolved : resolved.toString();
}

export function installDesktopFetchProxy(): void {
    if (import.meta.env.DEV || typeof window === 'undefined') {
        return;
    }

    const marker = '__rtvFetchProxied';
    if (marker in window) {
        return;
    }
    Object.defineProperty(window, marker, { value: true, enumerable: false });

    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
        if (!getApiBase()) {
            return originalFetch(input, init);
        }

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
