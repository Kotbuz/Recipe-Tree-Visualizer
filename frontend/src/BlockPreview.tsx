import { useEffect, useState } from 'react';
import './BlockPreview.css';

const candidateSuffixes = [
    { key: 'main', suffix: '' },
    { key: 'side', suffix: '_side' },
    { key: 'top', suffix: '_top' },
    { key: 'bottom', suffix: '_bottom' },
    { key: 'front', suffix: '_front' },
    { key: 'back', suffix: '_back' },
    { key: 'left', suffix: '_left' },
    { key: 'right', suffix: '_right' },
    { key: 'north', suffix: '_north' },
    { key: 'south', suffix: '_south' },
    { key: 'east', suffix: '_east' },
    { key: 'west', suffix: '_west' },
];

const buildFaces = (found: Record<string, string>) => {
    const choose = (...keys: Array<string | undefined>) => {
        for (const key of keys) {
            if (!key) continue;
            // if the key looks like a URL (we store found values as URLs starting with '/'), use it directly
            if (key.startsWith('/') || key.startsWith('http')) {
                return key;
            }
            const v = found[key];
            if (v) return v;
        }
        return undefined;
    };

    const top = choose('top', 'main');
    const bottom = choose('bottom', 'top', 'main');
    const side = choose('side', 'main');

    return {
        front: choose('front', 'north', side, 'main') ?? '',
        back: choose('back', 'south', side, 'main') ?? '',
        left: choose('left', 'west', side, 'main') ?? '',
        right: choose('right', 'east', side, 'main') ?? '',
        top: top ?? '',
        bottom: bottom ?? '',
    };
};

const maybeFetch = async (url: string) => {
    try {
        const response = await fetch(url, { method: 'HEAD' });
        if (response.ok) {
            return true;
        }
        return false;
    } catch {
        return false;
    }
};

const normalizeName = (name: string) => name.trim().replace(/\.png$/i, '').replace(/\s+/g, '_').toLowerCase();

// load image helper
const loadImage = (src: string) => new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
});

const variantBaseCandidates = (baseName: string) => {
    const candidates = [baseName];
    if (!baseName.endsWith('s')) {
        candidates.push(`${baseName}s`);
    }
    if (!baseName.endsWith('_planks')) {
        candidates.push(`${baseName}_planks`);
    }
    if (baseName.endsWith('_brick') && !baseName.endsWith('s')) {
        candidates.push(`${baseName}s`);
    }
    return Array.from(new Set(candidates));
};

const findVariantBaseTexture = async (baseName: string) => {
    const candidates = variantBaseCandidates(baseName);
    for (const candidate of candidates) {
        const url = `/block/${candidate}.png`;
        if (await maybeFetch(url)) {
            return url;
        }
    }
    return null;
};

// generate faces for slab or stairs from a single base texture
const generateVariantFaces = async (baseUrl: string, variant: 'slab' | 'stairs') => {
    const img = await loadImage(baseUrl);
    const w = img.naturalWidth || 64;
    const h = img.naturalHeight || w;

    const makeCanvas = (width: number, height: number) => {
        const c = document.createElement('canvas');
        c.width = width;
        c.height = height;
        return c;
    };

    // create top texture - use base as-is
    const topCanvas = makeCanvas(w, w);
    const topCtx = topCanvas.getContext('2d')!;
    topCtx.drawImage(img, 0, 0, w, w);

    // create side texture depending on variant
    const sideCanvas = makeCanvas(w + 2, w + 2); // slightly larger to overlap seams
    const sideCtx = sideCanvas.getContext('2d')!;

    if (variant === 'slab') {
        // take bottom half of base and scale to square
        sideCtx.drawImage(img, 0, Math.floor(h / 2), w, Math.ceil(h / 2), 0, 0, sideCanvas.width, sideCanvas.height);
    } else {
        // stairs: mask out upper-left quadrant
        sideCtx.drawImage(img, 0, 0, w, h, 0, 0, sideCanvas.width, sideCanvas.height);
        sideCtx.clearRect(0, 0, sideCanvas.width / 2, sideCanvas.height / 2);
        try {
            const imgData = sideCtx.getImageData(sideCanvas.width / 2, 0, sideCanvas.width / 2, sideCanvas.height / 2);
            sideCtx.putImageData(imgData, 0, 0);
        } catch {
            // ignore security / cross-origin issues
        }
    }

    const dataUrl = sideCanvas.toDataURL('image/png');
    const topDataUrl = topCanvas.toDataURL('image/png');

    return {
        front: dataUrl,
        back: dataUrl,
        left: dataUrl,
        right: dataUrl,
        top: topDataUrl,
        bottom: topDataUrl,
    } as { [key: string]: string };
};

interface BlockPreviewProps {
    blockName: string;
}

const BlockPreview = ({ blockName }: BlockPreviewProps) => {
    const [faces, setFaces] = useState<{ [key: string]: string } | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const normalized = normalizeName(blockName);
    const slabMatch = normalized.match(/^(.*)_slab$/);
    const stairsMatch = normalized.match(/^(.*)_stairs$/);
    const variant = slabMatch ? 'slab' : stairsMatch ? 'stairs' : 'normal';

    useEffect(() => {
        let active = true;
        const normalized = normalizeName(blockName);

        if (!normalized) {
            setError('Введите имя блока.');
            setFaces(null);
            return;
        }

        setLoading(true);
        setError(null);
        setFaces(null);

        const load = async () => {
            const found: Record<string, string> = {};
            await Promise.all(
                candidateSuffixes.map(async (candidate) => {
                    const url = `/block/${normalized}${candidate.suffix}.png`;
                    if (await maybeFetch(url)) {
                        found[candidate.key] = url;
                    }
                }),
            );

            if (!active) {
                return;
            }

            // if this is a slab or stairs variant, try to generate faces from base texture
            const slabMatch = normalized.match(/^(.*)_slab$/);
            const stairsMatch = normalized.match(/^(.*)_stairs$/);

            if (slabMatch || stairsMatch) {
                const baseName = (slabMatch || stairsMatch)![1];
                const baseUrl = await findVariantBaseTexture(baseName);
                if (baseUrl) {
                    try {
                        const generated = await generateVariantFaces(baseUrl, slabMatch ? 'slab' : 'stairs');
                        if (active) {
                            setFaces(generated);
                            setLoading(false);
                            return;
                        }
                    } catch (e) {
                        // fallback to normal behavior
                    }
                }
            }

            const result = buildFaces(found);
            if (!result.front || !result.top) {
                setError(`Не удалось найти текстуру для блока «${normalized}».`);
                setFaces(null);
            } else {
                setFaces(result);
            }
            setLoading(false);
        };

        void load();

        return () => {
            active = false;
        };
    }, [blockName]);

    return (
        <div className="block-preview-card">
            <h3>{blockName || 'Пустое имя блока'}</h3>
            <div className="block-preview-scene">
                {loading && <div className="block-preview-message">Загрузка текстур...</div>}
                {error && <div className="block-preview-message block-preview-error">{error}</div>}
                {!loading && faces && (
                    <div className={`block-preview-cube ${variant}`}>
                        <div className="block-face block-front" style={{ backgroundImage: `url(${faces.front})` }} />
                        <div className="block-face block-back" style={{ backgroundImage: `url(${faces.back})` }} />
                        <div className="block-face block-left" style={{ backgroundImage: `url(${faces.left})` }} />
                        <div className="block-face block-right" style={{ backgroundImage: `url(${faces.right})` }} />
                        <div className="block-face block-top" style={{ backgroundImage: `url(${faces.top})` }} />
                        <div className="block-face block-bottom" style={{ backgroundImage: `url(${faces.bottom})` }} />
                    </div>
                )}
            </div>
        </div>
    );
};

export default BlockPreview;
