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

interface BlockPreviewProps {
    blockName: string;
}

const BlockPreview = ({ blockName }: BlockPreviewProps) => {
    const [faces, setFaces] = useState<{ [key: string]: string } | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
                    <div className="block-preview-cube">
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
