export const DEFAULT_MINECRAFT_VERSION = '26.2';

export const RECIPE_SEARCH_DEBOUNCE_MS = 300;
export const RECIPE_SEARCH_LIMIT = 50;

/** Имя файла иконки из отображаемого названия предмета. */
export function normalizeItemFileName(itemName: string): string {
    return itemName.trim().replace(/\.png$/i, '').replace(/\s+/g, '_').toLowerCase();
}

const ICON_ALIASES: Readonly<Record<string, string>> = {
    planks: 'oak planks',
    logs: 'oak log',
    'logs that burn': 'oak log',
    'wooden tool materials': 'oak planks',
    'stone tool materials': 'cobblestone',
};

/** Обобщённые теги рецептов → конкретный предмет для иконки. */
export function resolveIconItemName(itemName: string): string {
    const normalized = itemName.trim().toLowerCase();
    return ICON_ALIASES[normalized] ?? itemName;
}

export function itemIconFileName(itemName: string): string {
    return `${normalizeItemFileName(resolveIconItemName(itemName))}.png`;
}

/** Имя PNG из icon_id, который приходит с бэкенда (IngredientRegistry). */
export function itemIconFileNameFromId(iconId: string): string {
    return `${normalizeItemFileName(iconId)}.png`;
}

export function resolveItemIconFileName(itemName: string, iconId?: string): string {
    if (iconId) {
        return itemIconFileNameFromId(iconId);
    }
    return itemIconFileName(itemName);
}
