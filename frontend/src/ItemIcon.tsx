import { useEffect, useState } from 'react';
import './ItemIcon.css';

const normalizeName = (name: string) => name.trim().replace(/\.png$/i, '').replace(/\s+/g, '_').toLowerCase();

interface ItemIconProps {
    itemName: string;
}

const ItemIcon = ({ itemName }: ItemIconProps) => {
    const [exists, setExists] = useState(false);
    const [loading, setLoading] = useState(true);
    const [url, setUrl] = useState('');

    useEffect(() => {
        const normalized = normalizeName(itemName);
        if (!normalized) {
            setLoading(false);
            setExists(false);
            setUrl('');
            return;
        }
        const candidate = `/item/${normalized}.png`;
        setLoading(true);
        setExists(false);
        setUrl(candidate);

        fetch(candidate, { method: 'HEAD' })
            .then((response) => {
                setExists(response.ok);
            })
            .catch(() => setExists(false))
            .finally(() => setLoading(false));
    }, [itemName]);

    return (
        <div className="item-icon-card">
            <h3>Иконка предмета</h3>
            {loading ? (
                <div className="item-icon-message">Проверка...</div>
            ) : exists ? (
                <img className="item-icon-image" src={url} alt={itemName} />
            ) : (
                <div className="item-icon-message">Иконка не найдена</div>
            )}
            <div className="item-icon-label">{itemName}</div>
        </div>
    );
};

export default ItemIcon;
