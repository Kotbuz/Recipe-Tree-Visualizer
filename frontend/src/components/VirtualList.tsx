import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import '../styles/VirtualList.css';

type VirtualListProps<T> = {
    items: T[];
    itemHeight: number;
    className?: string;
    renderItem: (item: T, index: number) => ReactNode;
    getItemKey: (item: T, index: number) => string;
};

export default function VirtualList<T>({
    items,
    itemHeight,
    className = '',
    renderItem,
    getItemKey,
}: VirtualListProps<T>) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [viewportHeight, setViewportHeight] = useState(320);
    const [scrollTop, setScrollTop] = useState(0);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        const updateHeight = () => {
            setViewportHeight(element.clientHeight);
        };

        updateHeight();
        const observer = new ResizeObserver(updateHeight);
        observer.observe(element);

        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        setScrollTop(0);
        if (containerRef.current) {
            containerRef.current.scrollTop = 0;
        }
    }, [items]);

    const handleScroll = useCallback(() => {
        if (!containerRef.current) return;
        setScrollTop(containerRef.current.scrollTop);
    }, []);

    const totalHeight = items.length * itemHeight;
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 2);
    const endIndex = Math.min(
        items.length,
        Math.ceil((scrollTop + viewportHeight) / itemHeight) + 2,
    );
    const offsetY = startIndex * itemHeight;

    return (
        <div
            ref={containerRef}
            className={`virtual-list ${className}`.trim()}
            onScroll={handleScroll}
        >
            <div className="virtual-list-spacer" style={{ height: totalHeight }}>
                <div className="virtual-list-window" style={{ transform: `translateY(${offsetY}px)` }}>
                    {items.slice(startIndex, endIndex).map((item, index) => {
                        const absoluteIndex = startIndex + index;
                        return (
                            <div
                                key={getItemKey(item, absoluteIndex)}
                                className="virtual-list-item"
                                style={{ height: itemHeight }}
                            >
                                {renderItem(item, absoluteIndex)}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
