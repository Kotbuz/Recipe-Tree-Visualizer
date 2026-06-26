import type { RecipeItem } from '../types/recipe';

const AIR_ITEM_ID = 'minecraft:air';

export const mergeRecipeItems = (items: RecipeItem[]): RecipeItem[] => {
    const merged = new Map<string, RecipeItem>();

    for (const item of items) {
        if (item.item_id === AIR_ITEM_ID) {
            continue;
        }

        const key = `${item.item_id ?? item.name}:${item.metadata ?? ''}`;
        const existing = merged.get(key);
        if (existing) {
            existing.amount += item.amount;
            continue;
        }

        merged.set(key, { ...item });
    }

    return Array.from(merged.values());
};
