import { itemsMatch } from '../types/recipe';

export type IngredientRef = {
    name: string;
    itemId?: string;
};

export type IngredientIndex = {
    tags: Readonly<Record<string, readonly string[]>>;
    aliases: Readonly<Record<string, string>>;
};

const normalizeKey = (value: string) => value.trim().toLowerCase();

export const itemIdToDisplayName = (itemId: string): string => {
    const raw = itemId.replace(/^tag:/, '');
    const path = raw.includes(':') ? raw.split(':', 2)[1]! : raw;
    return path.replace(/_/g, ' ');
};

const normalizeTagId = (raw: string): string => {
    const cleaned = raw.trim().replace(/^#/, '');
    return cleaned.startsWith('tag:') ? cleaned : `tag:${cleaned}`;
};

const needleToTagId = (needle: string, index: IngredientIndex): string | null => {
    const normalized = normalizeKey(needle);
    if (normalized.startsWith('tag:')) {
        return normalizeTagId(normalized);
    }

    for (const tagId of Object.keys(index.tags)) {
        if (itemIdToDisplayName(tagId).toLowerCase() === normalized) {
            return tagId;
        }
    }

    return null;
};

const itemIdsEquivalent = (left: string, right: string): boolean => {
    const a = normalizeKey(left);
    const b = normalizeKey(right);
    if (a === b) {
        return true;
    }
    return a.split(':', 2).pop() === b.split(':', 2).pop();
};

const isMemberOfTag = (itemId: string, tagId: string, index: IngredientIndex): boolean => {
    const members = index.tags[tagId];
    if (!members?.length) {
        return false;
    }
    return members.some((member) => itemIdsEquivalent(itemId, member));
};

/** Один проход сопоставления — зеркало IngredientRegistry.ingredient_matches на бэкенде. */
export const ingredientMatches = (
    needle: string,
    ingredientId: string,
    index: IngredientIndex,
): boolean => {
    const normalizedNeedle = normalizeKey(needle);
    if (!normalizedNeedle) {
        return false;
    }

    const normalizedId = ingredientId.trim();
    const displayName = itemIdToDisplayName(normalizedId).toLowerCase();
    const alias = (index.aliases[displayName] ?? displayName).toLowerCase();
    const candidates = [normalizeKey(normalizedId), displayName, alias];

    if (candidates.some(
        (candidate) =>
            itemsMatch(normalizedNeedle, candidate) ||
            itemIdsEquivalent(normalizedNeedle, candidate),
    )) {
        return true;
    }

    const needleTagId = needleToTagId(normalizedNeedle, index);
    if (needleTagId && isMemberOfTag(normalizedId, needleTagId, index)) {
        return true;
    }

    if (normalizedId.toLowerCase().startsWith('tag:')) {
        const tagId = normalizeTagId(normalizedId);
        const members = index.tags[tagId] ?? [];
        for (const memberId of members) {
            if (ingredientMatches(normalizedNeedle, memberId, index)) {
                return true;
            }
        }
    }

    return false;
};

/** Двунаправленная совместимость, как IFocus в JEI / BipartiteGraphEngine._item_matches. */
export const ingredientsCompatible = (
    left: IngredientRef,
    right: IngredientRef,
    index: IngredientIndex | null,
): boolean => {
    if (!left.name || !right.name) {
        return false;
    }

    if (!index) {
        return itemsMatch(left.name, right.name);
    }

    const leftKey = left.itemId ?? left.name;
    const rightKey = right.itemId ?? right.name;

    if (itemIdsEquivalent(leftKey, rightKey)) {
        return true;
    }

    if (ingredientMatches(leftKey, rightKey, index)) {
        return true;
    }
    if (ingredientMatches(rightKey, leftKey, index)) {
        return true;
    }

    return itemsMatch(left.name, right.name) || itemIdsEquivalent(leftKey, rightKey);
};
