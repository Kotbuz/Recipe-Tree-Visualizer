import { useEffect, useState } from 'react';
import BlockPreview from './BlockPreview';

export default function PreviewPage() {
    const [available, setAvailable] = useState<string[]>([]);
    const [left, setLeft] = useState('acacia_log');
    const [right, setRight] = useState('furnace');

    useEffect(() => {
        let active = true;
        // request full list: count=0 returns full filtered list
        fetch('/api/blocks?count=0&type=block')
            .then((r) => r.json())
            .then((list: Array<{ type: string; name: string }>) => {
                if (!active) return;
                setAvailable(list.map((i) => i.name));
            })
            .catch(() => {
                /* ignore */
            });
        return () => {
            active = false;
        };
    }, []);

    const rand = () => {
        if (!available || available.length === 0) return;
        const pick = (exclude?: string) => {
            let i = Math.floor(Math.random() * available.length);
            let tries = 0;
            while (available[i] === exclude && tries < 10) {
                i = Math.floor(Math.random() * available.length);
                tries++;
            }
            return available[i];
        };
        const a = pick();
        const b = pick(a);
        setLeft(a);
        setRight(b);
    };

    return (
        <div>
            <div style={{ textAlign: 'center', marginBottom: 12 }}>
                <button onClick={rand}>Randomize blocks</button>
            </div>
            <div className="preview-grid">
                <BlockPreview blockName={left} />
                <BlockPreview blockName={right} />
            </div>
        </div>
    );
}
