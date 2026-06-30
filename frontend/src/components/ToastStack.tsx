import type { ToastItem } from '../hooks/useToast';
import '../styles/ToastStack.css';

type ToastStackProps = {
    toasts: ToastItem[];
    onDismiss: (id: number) => void;
};

export default function ToastStack({ toasts, onDismiss }: ToastStackProps) {
    if (toasts.length === 0) {
        return null;
    }

    return (
        <div className="toast-stack" aria-live="polite" aria-relevant="additions">
            {toasts.map((toast) => (
                <div key={toast.id} className={`toast toast--${toast.variant}`} role="status">
                    <span className="toast-message">{toast.message}</span>
                    <button
                        type="button"
                        className="toast-dismiss"
                        aria-label="Закрыть"
                        onClick={() => onDismiss(toast.id)}
                    >
                        ×
                    </button>
                </div>
            ))}
        </div>
    );
}
