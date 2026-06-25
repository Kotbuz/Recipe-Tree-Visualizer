export const DEFAULT_MINECRAFT_VERSION = '26.2';

export const RECIPE_SEARCH_DEBOUNCE_MS = 300;
export const RECIPE_SEARCH_LIMIT = 50;

/** Имя файла иконки из отображаемого названия предмета. */
export function normalizeItemFileName(itemName: string): string {
    return itemName.trim().replace(/\.png$/i, '').replace(/\s+/g, '_').toLowerCase();
}

export function itemIconFileName(itemName: string): string {
    return `${normalizeItemFileName(itemName)}.png`;
}
