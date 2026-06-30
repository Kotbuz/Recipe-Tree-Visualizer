import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, promises as fs } from 'fs';
import { extname, resolve } from 'path';

const assetRoot = resolve(__dirname, '..', 'Minecraft versions', '26.2');
const fsFolderMap: Record<string, string> = {
    block: 'block-textures',
    item: 'item-textures'
};
const validFolders = new Set(Object.keys(fsFolderMap));
const imageExtensions = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif']);

const fileExists = async (path: string) => {
    try {
        const stat = await fs.stat(path);
        return stat.isFile();
    } catch {
        return false;
    }
};

const isTauriBuild = Boolean(process.env.TAURI_ENV_PLATFORM);

export default defineConfig({
    define: {
        __RTV_DESKTOP__: JSON.stringify(isTauriBuild),
    },
    plugins: [
        react(),
        {
            name: 'mc-assets',
            configureServer(server) {
                server.middlewares.use(async (req, res, next) => {
                    const url = req.url || '';

                    // API: list blocks/items and random selection based on item JSONs
                    if (url.startsWith('/api/blocks')) {
                        try {
                            const u = new URL(url, 'http://localhost');
                            const count = Number(u.searchParams.get('count') || '2');
                            const typeFilter = u.searchParams.get('type') || 'block';

                            const itemsDir = resolve(assetRoot, 'items');
                            const files = await fs.readdir(itemsDir);
                            const results: Array<{ type: string; name: string }> = [];

                            for (const f of files) {
                                if (!f.endsWith('.json')) continue;
                                const full = resolve(itemsDir, f);
                                try {
                                    const txt = await fs.readFile(full, 'utf8');
                                    const m = txt.match(/minecraft:(block|item)\/([-a-z0-9_]+)/i);
                                    if (m) {
                                        results.push({ type: m[1].toLowerCase(), name: m[2] });
                                    }
                                } catch (e) {
                                    // ignore
                                }
                            }

                            const filtered = results.filter((r) => r.type === typeFilter);
                            // if count==0 or not specified, return full list
                            if (!count) {
                                res.setHeader('Content-Type', 'application/json');
                                res.statusCode = 200;
                                return res.end(JSON.stringify(filtered));
                            }

                            const picked: Array<{ type: string; name: string }> = [];
                            const pool = [...filtered];
                            for (let i = 0; i < count && pool.length > 0; i++) {
                                const idx = Math.floor(Math.random() * pool.length);
                                picked.push(pool.splice(idx, 1)[0]);
                            }

                            res.setHeader('Content-Type', 'application/json');
                            res.statusCode = 200;
                            return res.end(JSON.stringify(picked));
                        } catch (err) {
                            res.statusCode = 500;
                            return res.end('error');
                        }
                    }

                    if (!url.startsWith('/block/') && !url.startsWith('/item/')) {
                        return next();
                    }

                    console.log('[vite-middleware] asset request:', url);

                    const parts = url.split('/').filter(Boolean);
                    if (parts.length !== 2) {
                        console.log('[vite-middleware] unexpected parts:', parts);
                        return next();
                    }

                    const [folder, fileName] = parts;
                    if (!validFolders.has(folder)) {
                        console.log('[vite-middleware] invalid folder:', folder);
                        return next();
                    }

                    const mapped = fsFolderMap[folder];
                    const filePath = resolve(assetRoot, mapped, fileName);
                    const extension = extname(filePath).toLowerCase();
                    if (!imageExtensions.has(extension)) {
                        console.log('[vite-middleware] invalid extension:', extension);
                        return next();
                    }

                    const exists = await fileExists(filePath);
                    console.log('[vite-middleware] filePath:', filePath, 'exists:', exists);
                    if (!exists) {
                        res.statusCode = 404;
                        return res.end('Not found');
                    }

                    res.statusCode = 200;
                    res.setHeader('Content-Type', 'image/png');
                    createReadStream(filePath).pipe(res);
                });
            }
        }
    ],
    server: {
        port: 5173,
        middlewareMode: false,
        proxy: {
            // `/api/...` → backend (без префикса). `/api/blocks` перехватывает middleware выше.
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                rewrite: (path: string) => path.replace(/^\/api/, ''),
            },
            '/recipes': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/versions': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/mods': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/modpack': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/settings': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/items': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/graph': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
        fs: {
            allow: [assetRoot, resolve(__dirname)]
        }
    }
});
