import { useEffect, useState } from 'react';

type MachineLimitInputProps = {
    nodeId: string;
    machineLimit: number | null | undefined;
    onCommit: (value: number | null) => void;
};

export default function MachineLimitInput({
    nodeId,
    machineLimit,
    onCommit,
}: MachineLimitInputProps) {
    const [draft, setDraft] = useState('');

    useEffect(() => {
        setDraft(machineLimit != null ? String(machineLimit) : '');
    }, [machineLimit, nodeId]);

    const commit = () => {
        const trimmed = draft.trim();
        if (!trimmed) {
            onCommit(null);
            return;
        }
        const parsed = Number.parseInt(trimmed, 10);
        if (Number.isFinite(parsed) && parsed >= 1) {
            onCommit(parsed);
            setDraft(String(parsed));
        } else {
            setDraft(machineLimit != null ? String(machineLimit) : '');
        }
    };

    return (
        <input
            className="recipe-node-limit-input"
            type="text"
            inputMode="numeric"
            aria-label="Лимит машин"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
                event.stopPropagation();
                if (event.key === 'Enter') {
                    event.preventDefault();
                    commit();
                    event.currentTarget.blur();
                }
            }}
            onMouseDown={(event) => event.stopPropagation()}
            onPointerDown={(event) => event.stopPropagation()}
        />
    );
}
