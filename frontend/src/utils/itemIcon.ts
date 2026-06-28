export const DEFAULT_MINECRAFT_VERSION = '26.2';

export const RECIPE_SEARCH_DEBOUNCE_MS = 400;
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
    leathers: 'leather',
    'treated wood': 'treated wood horizontal',
};

/** Обобщённые теги рецептов → конкретный предмет для иконки. */
export function resolveIconItemName(itemName: string): string {
    const normalized = itemName.trim().toLowerCase();
    return ICON_ALIASES[normalized] ?? itemName;
}

export function itemIconFileName(itemName: string): string {
    return `${normalizeItemFileName(resolveIconItemName(itemName))}.png`;
}

/** Нормализует icon_id с бэкенда (minecraft:oak_planks → oak_planks, alltheores:quartz_dust → alltheores_quartz_dust). */
export function normalizeIconId(iconId: string): string {
    const trimmed = iconId.trim().replace(/\.png$/i, '');
    if (trimmed.includes(':')) {
        const [namespace, path] = trimmed.split(':', 2);
        const normalizedPath = path.replace(/\s+/g, '_').toLowerCase();
        if (namespace !== 'minecraft') {
            return `${namespace}_${normalizedPath}`;
        }
        return normalizedPath;
    }
    return trimmed.replace(/\s+/g, '_').toLowerCase();
}

/** Имя PNG из icon_id, который приходит с бэкенда (IngredientRegistry). */
export function itemIconFileNameFromId(iconId: string): string {
    const normalized = normalizeIconId(iconId);
    const aliased = ICON_ALIASES[normalized.replace(/_/g, ' ')] ?? normalized;
    const resolved = aliased.includes(' ') ? normalizeItemFileName(aliased) : aliased;
    return `${resolved}.png`;
}

export function resolveItemIconFileName(itemName: string, iconId?: string): string {
    if (iconId) {
        return itemIconFileNameFromId(iconId);
    }
    return itemIconFileName(itemName);
}
