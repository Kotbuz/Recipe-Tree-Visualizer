import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    applyWheelZoom,
    buildTransformStyle,
    createCanvasCoordSystem,
    DEFAULT_CANVAS_TRANSFORM,
    type CanvasCoordSystem,
    type CanvasTransform,
    toViewportRect,
} from './canvasCoords';

export function useCanvasViewport() {
    const viewportRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const [transform, setTransform] = useState<CanvasTransform>(DEFAULT_CANVAS_TRANSFORM);
    const [rect, setRect] = useState<ReturnType<typeof toViewportRect> | null>(null);
    const [isPanning, setIsPanning] = useState(false);
    const panStartRef = useRef<{ x: number; y: number } | null>(null);

    const updateRect = useCallback(() => {
        const element = viewportRef.current;
        if (!element) return;
        setRect(toViewportRect(element.getBoundingClientRect()));
    }, []);

    useEffect(() => {
        updateRect();
        const element = viewportRef.current;
        if (!element) return;

        const observer = new ResizeObserver(updateRect);
        observer.observe(element);
        window.addEventListener('resize', updateRect);

        return () => {
            observer.disconnect();
            window.removeEventListener('resize', updateRect);
        };
    }, [updateRect]);

    const coords: CanvasCoordSystem = useMemo(
        () => createCanvasCoordSystem(transform, rect),
        [transform, rect],
    );

    const setViewportTransform = useCallback((next: CanvasTransform) => {
        setTransform(next);
    }, []);

    const handleWheel = useCallback(
        (event: React.WheelEvent<HTMLDivElement>) => {
            event.preventDefault();
            if (!rect) return;

            const pointerX = event.clientX - rect.left;
            const pointerY = event.clientY - rect.top;
            setTransform((current) => applyWheelZoom(current, pointerX, pointerY, event.deltaY));
        },
        [rect],
    );

    const handlePanMouseDown = useCallback(
        (event: React.MouseEvent<HTMLDivElement>) => {
            if (event.button !== 0 || !rect) return false;

            panStartRef.current = {
                x: event.clientX - rect.left - transform.offsetX,
                y: event.clientY - rect.top - transform.offsetY,
            };
            setIsPanning(true);
            return true;
        },
        [rect, transform.offsetX, transform.offsetY],
    );

    const handlePanMouseMove = useCallback(
        (event: React.MouseEvent<HTMLDivElement>) => {
            const panStart = panStartRef.current;
            if (!isPanning || !panStart || !rect) return;

            const offsetX = event.clientX - rect.left - panStart.x;
            const offsetY = event.clientY - rect.top - panStart.y;

            setTransform((current) => ({
                ...current,
                offsetX,
                offsetY,
            }));
        },
        [isPanning, rect],
    );

    const handlePanMouseUp = useCallback(() => {
        setIsPanning(false);
        panStartRef.current = null;
    }, []);

    const transformStyle = useMemo(() => buildTransformStyle(transform), [transform]);

    return {
        viewportRef,
        contentRef,
        transform,
        transformStyle,
        coords,
        isPanning,
        setViewportTransform,
        handleWheel,
        handlePanMouseDown,
        handlePanMouseMove,
        handlePanMouseUp,
        updateRect,
    };
}
