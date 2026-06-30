import type { OperationStatusLine } from '../utils/operationStatus';
import '../styles/OperationStatusBar.css';

type OperationStatusBarProps = {
    lines: OperationStatusLine[];
    compact?: boolean;
};

export default function OperationStatusBar({ lines, compact = false }: OperationStatusBarProps) {
    return (
        <div
            className={`operation-status-bar${compact ? ' operation-status-bar--compact' : ''}`}
            role="status"
            aria-live="polite"
        >
            {lines.map((line) => (
                <span
                    key={line.key}
                    className={`operation-status-line operation-status-line--${line.tone}${
                        line.active ? ' operation-status-line--active' : ''
                    }`}
                    title={line.text}
                >
                    <span className="operation-status-label">{line.label}:</span>
                    <span className="operation-status-text">{line.text}</span>
                    {line.active ? (
                        <span className="operation-status-spinner" aria-hidden />
                    ) : null}
                </span>
            ))}
        </div>
    );
}
