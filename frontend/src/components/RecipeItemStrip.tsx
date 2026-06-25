import type { RecipeItem } from '../types/recipe';
import ItemIconView from './ItemIconView';
import '../styles/RecipeItemStrip.css';

type RecipeItemStripProps = {
    items: RecipeItem[];
    className?: string;
};

export default function RecipeItemStrip({ items, className = '' }: RecipeItemStripProps) {
    return (
        <div className={`recipe-item-strip ${className}`.trim()}>
            {items.map((item, index) => (
                <ItemIconView key={`${item.name}-${index}`} itemName={item.name} />
            ))}
        </div>
    );
}
