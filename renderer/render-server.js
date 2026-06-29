import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import AdmZip from 'adm-zip';
import { prepareAssets, renderBlock, renderItem } from 'block-model-renderer';
import express from 'express';

const PORT = Number(process.env.PORT ?? 3001);
const PROJECT_ROOT = path.resolve(fileURLToPath(new URL('.', import.meta.url)), '..');
const LOCAL_MINECRAFT_ROOT = path.resolve(PROJECT_ROOT, 'MinecraftVersions');
const ALLOWED_ROOTS = (process.env.ALLOWED_ROOTS ?? '/data/mods,/data/rendered,/data/minecraft')
    .split(',')
    .map((entry) => path.resolve(entry.trim()))
    .filter(Boolean);
if (!ALLOWED_ROOTS.some((root) => root === LOCAL_MINECRAFT_ROOT)) {
    ALLOWED_ROOTS.push(LOCAL_MINECRAFT_ROOT);
}
const RENDER_TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS ?? 600_000);
const DEFAULT_MINECRAFT_VERSION = process.env.MINECRAFT_VERSION ?? '1.21.4';

const app = express();
app.use(express.json({ limit: '1mb' }));

function resolveAllowedPath(targetPath, label) {
    if (typeof targetPath !== 'string' || !targetPath.trim()) {
        throw new Error(`${label} is required`);
    }

    const resolved = path.resolve(targetPath);
    const allowed = ALLOWED_ROOTS.some(
        (root) => resolved === root || resolved.startsWith(`${root}${path.sep}`),
    );
    if (!allowed) {
        throw new Error(`${label} is outside allowed directories`);
    }

    return resolved;
}

async function listPngFiles(directory) {
    try {
        const entries = await fs.readdir(directory, { withFileTypes: true });
        return entries
            .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.png'))
            .map((entry) => entry.name)
            .sort();
    } catch (error) {
        if (error && error.code === 'ENOENT') {
            return [];
        }
        throw error;
    }
}

function normalizeFilter(filter) {
    if (!Array.isArray(filter) || filter.length === 0) {
        return null;
    }

    const names = filter
        .map((entry) => String(entry).trim())
        .filter(Boolean)
        .map((entry) => entry.replace(/\.png$/i, ''));
    return names.length > 0 ? names : null;
}

function createJarAssets(jarPath) {
    const zip = new AdmZip(jarPath);
    const entries = zip.getEntries();
    const fileMap = new Map();

    for (const entry of entries) {
        if (entry.isDirectory) {
            continue;
        }
        const entryName = entry.entryName.replace(/\\/g, '/');
        fileMap.set(entryName, entry);
    }

    return {
        async read(filePath) {
            const normalized = filePath.replace(/\\/g, '/').replace(/^\//, '');
            const zipEntry = fileMap.get(normalized);
            if (!zipEntry) {
                return null;
            }
            return zipEntry.getData();
        },
        list(directory) {
            const normalized = directory.replace(/\\/g, '/').replace(/^\//, '').replace(/\/$/, '');
            const prefix = normalized ? `${normalized}/` : '';
            const names = new Set();

            for (const entryName of fileMap.keys()) {
                if (!entryName.startsWith(prefix)) {
                    continue;
                }
                const rest = entryName.slice(prefix.length);
                const slashIndex = rest.indexOf('/');
                if (slashIndex === -1) {
                    names.add(rest);
                } else {
                    names.add(rest.slice(0, slashIndex));
                }
            }

            return Array.from(names);
        },
    };
}

async function renderSingleIcon(assets, iconName, outputPath, width, height, minecraftVersion) {
    const baseOptions = {
        assets,
        id: iconName,
        path: outputPath,
        width: width ?? 128,
        height: height ?? 128,
        animated: false,
        version: minecraftVersion,
    };

    // Блоки (доски, iron_block) — сначала 3D-модель блока; предметы (лодка) — item.
    const attempts = [
        ['block', renderBlock],
        ['item', renderItem],
    ];

    let lastError = null;
    for (const [, renderFn] of attempts) {
        try {
            await renderFn(baseOptions);
            return { name: iconName };
        } catch (error) {
            lastError = error;
        }
    }

    const reason =
        lastError instanceof Error ? lastError.message : 'render failed';
    return { name: iconName, skipped: reason };
}

async function renderIcons({
    jarPath,
    modJarPaths,
    outputDir,
    filter,
    width,
    height,
    noAnimation,
    minecraftVersion,
}) {
    const handlers = [createJarAssets(jarPath)];
    for (const extraJar of modJarPaths ?? []) {
        if (typeof extraJar === 'string' && extraJar.trim()) {
            handlers.push(createJarAssets(extraJar));
        }
    }

    const assets = await prepareAssets(handlers);
    const names = normalizeFilter(filter);
    if (!names) {
        throw new Error('filter must contain at least one icon name');
    }

    const rendered = [];
    const skipped = [];

    for (const iconName of names) {
        const outputPath = path.join(outputDir, `${iconName}.png`);
        const result = await renderSingleIcon(
            assets,
            iconName,
            outputPath,
            width,
            height,
            minecraftVersion,
        );

        if (result.skipped) {
            skipped.push({ name: iconName, reason: result.skipped });
            continue;
        }

        rendered.push(`${iconName}.png`);
    }

    if (noAnimation === false) {
        // block-model-renderer uses animated=false above; flag kept for API compatibility.
    }

    return { rendered, skipped };
}

function withTimeout(promise, timeoutMs) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            reject(new Error(`Render timed out after ${timeoutMs}ms`));
        }, timeoutMs);

        promise
            .then((value) => {
                clearTimeout(timer);
                resolve(value);
            })
            .catch((error) => {
                clearTimeout(timer);
                reject(error);
            });
    });
}

app.get('/health', (_request, response) => {
    response.json({
        status: 'ok',
        service: 'recipe-tree-renderer',
        engine: 'block-model-renderer',
        allowed_roots: ALLOWED_ROOTS,
    });
});

app.post('/render', async (request, response) => {
    try {
        const jarPath = resolveAllowedPath(request.body?.jar_path, 'jar_path');
        const outputDir = resolveAllowedPath(request.body?.output_dir, 'output_dir');

        await fs.access(jarPath);
        await fs.mkdir(outputDir, { recursive: true });

        const before = new Set(await listPngFiles(outputDir));
        const renderResult = await withTimeout(
            renderIcons({
                jarPath,
                modJarPaths: request.body?.mod_jar_paths,
                outputDir,
                filter: request.body?.filter,
                width: request.body?.width,
                height: request.body?.height,
                noAnimation: request.body?.no_animation,
                minecraftVersion: request.body?.minecraft_version ?? DEFAULT_MINECRAFT_VERSION,
            }),
            RENDER_TIMEOUT_MS,
        );

        const after = await listPngFiles(outputDir);
        const newlyRendered = after.filter((fileName) => !before.has(fileName));

        response.json({
            status: 'done',
            jar_path: jarPath,
            output_dir: outputDir,
            rendered: newlyRendered.length > 0 ? newlyRendered : renderResult.rendered,
            total_icons: after.length,
            skipped: renderResult.skipped,
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Render failed';
        const statusCode = message.includes('outside allowed') ? 403 : 400;
        response.status(statusCode).json({
            status: 'error',
            error: message,
        });
    }
});

app.listen(PORT, () => {
    console.log(`Renderer listening on :${PORT}`);
    console.log(`Engine: block-model-renderer`);
    console.log(`Allowed roots: ${ALLOWED_ROOTS.join(', ')}`);
});
