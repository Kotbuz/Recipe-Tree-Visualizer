import { useEffect, useMemo, useState } from 'react';
import { useMinecraftVersion } from '../context/MinecraftVersionContext';
import { resolveItemIconFileName } from '../utils/itemIcon';
import '../styles/ItemIconView.css';

type ItemIconViewProps = {
    itemName: string;
    iconId?: string;
    title?: string;
    className?: string;
};

const splitChipLabel = (itemName: string) => {
    const words = itemName.trim().split(/\s+/);
    if (words.length <= 1) {
        return itemName.slice(0, 3).toUpperCase();
    }
    return words
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase() ?? '')
        .join('');
};

export default function ItemIconView({
    itemName,
    iconId,
    title,
    className = '',
}: ItemIconViewProps) {
    const { itemIconUrl } = useMinecraftVersion();
    const label = title ?? itemName;
    const [sourceIndex, setSourceIndex] = useState(0);

    const iconSources = useMemo(() => {
        const fileName = resolveItemIconFileName(itemName, iconId);
        const textureId = fileName.replace(/\.png$/i, '');
        return [
            itemIconUrl(itemName, iconId),
            `/block/${textureId}.png`,
            `/item/${textureId}.png`,
        ].filter((url): url is string => Boolean(url));
    }, [iconId, itemIconUrl, itemName]);

    useEffect(() => {
        setSourceIndex(0);
    }, [iconSources]);

    const iconUrl = iconSources[sourceIndex] ?? null;

    if (iconUrl && sourceIndex < iconSources.length) {
        return (
            <img
                className={`item-icon-view item-icon-view--image ${className}`.trim()}
                src={iconUrl}
                alt={label}
                title={label}
                draggable={false}
                onError={() => {
                    setSourceIndex((current) => current + 1);
                }}
            />
        );
    }

    return (
        <span
            className={`item-icon-view item-icon-view--chip ${className}`.trim()}
            title={label}
            aria-label={label}
        >
            {splitChipLabel(itemName)}
        </span>
    );
}
