import { useEffect, useState } from 'react';
import { useMinecraftVersion } from '../context/MinecraftVersionContext';
import '../styles/ItemIconView.css';

type ItemIconViewProps = {
    itemName: string;
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

export default function ItemIconView({ itemName, title, className = '' }: ItemIconViewProps) {
    const { itemIconUrl } = useMinecraftVersion();
    const iconUrl = itemIconUrl(itemName);
    const label = title ?? itemName;
    const [imageFailed, setImageFailed] = useState(false);

    useEffect(() => {
        setImageFailed(false);
    }, [itemName, iconUrl]);

    if (iconUrl && !imageFailed) {
        return (
            <img
                className={`item-icon-view item-icon-view--image ${className}`.trim()}
                src={iconUrl}
                alt={label}
                title={label}
                draggable={false}
                onError={() => {
                    setImageFailed(true);
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
