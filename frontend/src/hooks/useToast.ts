import { useCallback, useState } from 'react';

export type ToastVariant = 'info' | 'success' | 'warn' | 'error';

export type ToastItem = {
    id: number;
    message: string;
    variant: ToastVariant;
};

const TOAST_TTL_MS = 6000;

export function useToast() {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const dismiss = useCallback((id: number) => {
        setToasts((current) => current.filter((item) => item.id !== id));
    }, []);

    const push = useCallback(
        (message: string, variant: ToastVariant = 'info') => {
            const id = Date.now() + Math.floor(Math.random() * 1000);
            setToasts((current) => [...current, { id, message, variant }]);
            window.setTimeout(() => dismiss(id), TOAST_TTL_MS);
        },
        [dismiss],
    );

    return { toasts, push, dismiss };
}
