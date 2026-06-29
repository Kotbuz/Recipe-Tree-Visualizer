import { itemsMatch } from '../types/recipe';

export type IngredientRef = {
    name: string;
    itemId?: string;
    metadata?: number;
};

export type IngredientIndex = {
    tags: Readonly<Record<string, readonly string[]>>;
    aliases: Readonly<Record<string, string>>;
};

const normalizeKey = (value: string) => value.trim().toLowerCase();

export const itemIdToDisplayName = (itemId: string): string => {
    const common = commonTagDisplayName(itemId);
    if (common) {
        return common;
    }
    const raw = itemId.replace(/^tag:/, '');
    const path = raw.includes(':') ? raw.split(':', 2)[1]! : raw;
    return path.replace(/_/g, ' ');
};

const CATEGORY_LABELS: Record<string, string> = {
    dusts: 'dust',
    gems: '',
    gears: 'gear',
    rods: 'rod',
    plates: 'plate',
    ingots: 'ingot',
    nuggets: 'nugget',
    ores: 'ore',
    raw_materials: 'raw',
    storage_blocks: 'block',
    glass_blocks: 'glass block',
    blocks: 'block',
    leathers: 'leather',
    wires: 'wire',
    coins: 'coin',
};

const MOD_MATERIAL_PREFIXES = new Set([
    'alltheores',
    'mekanism',
    'actuallyadditions',
    'immersiveengineering',
    'ae2',
    'appliedenergistics2',
    'create',
    'thermal',
    'enderio',
    'techopolis',
]);

const humanizeTagMaterial = (rawMaterial: string): string => {
    const parts = rawMaterial.replace(/_/g, ' ').split(/\s+/).filter(Boolean);
    if (parts.length >= 2 && MOD_MATERIAL_PREFIXES.has(parts[0]!.toLowerCase())) {
        return parts.slice(1).join(' ');
    }
    return parts.join(' ');
};

export const commonTagDisplayName = (itemId: string): string | null => {
    const normalized = itemId.startsWith('tag:') ? itemId : itemId.startsWith('#') ? `tag:${itemId.slice(1)}` : null;
    if (!normalized?.startsWith('tag:c:')) {
        return null;
    }

    const path = normalized.slice('tag:c:'.length);
    const segments = path.split('/').filter(Boolean).map((part) => part.replace(/_/g, ' '));
    if (!segments.length) {
        return null;
    }
    if (segments.length === 1) {
        return titleCase(segments[0]!);
    }

    const category = path.split('/', 1)[0]!;
    const material = humanizeTagMaterial(segments[segments.length - 1]!);
    const materialTitle = titleCase(material);

    if (category === 'glass_blocks' && material === 'cheap') {
        return 'Cheap Glass Block';
    }
    if (category === 'glass_blocks') {
        return `${materialTitle} Glass Block`;
    }

    const suffix = CATEGORY_LABELS[category];
    if (suffix !== undefined) {
        if (suffix && materialTitle.toLowerCase().endsWith(` ${suffix}`)) {
            return materialTitle;
        }
        if (suffix) {
            return `${materialTitle} ${titleCase(suffix)}`;
        }
        return materialTitle;
    }

    if (segments.length === 2) {
        return `${materialTitle} (${titleCase(segments[0]!)})`;
    }

    return segments.map((segment) => titleCase(segment)).join(' / ');
};

const titleCase = (value: string): string =>
    value
        .split(' ')
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

const normalizeTagId = (raw: string): string => {
    const cleaned = raw.trim().replace(/^#/, '');
    return cleaned.startsWith('tag:') ? cleaned : `tag:${cleaned}`;
};

/** AE2: ae2:CableCovered в рецепте = Fluix ME Covered Cable в игре. */
const AE2_CABLE_FAMILIES = new Set([
    'CableGlass',
    'CableCovered',
    'CableSmart',
    'CableDense',
    'CableAnchor',
]);
const AE2_MATERIAL_VARIANTS = new Set(['Fluix', 'Quartz']);

const ae2ItemFamilyParts = (itemId: string): { family: string; variant: string | null } | null => {
    const normalized = itemId.trim().toLowerCase();
    const prefix = 'appliedenergistics2:item.';
    if (!normalized.startsWith(prefix)) {
        return null;
    }

    const rest = itemId.split(':', 2)[1]!.replace(/^item\./i, '').toLowerCase();
    const exactFamily = [...AE2_CABLE_FAMILIES].find((entry) => entry.toLowerCase() === rest);
    if (exactFamily) {
        return { family: exactFamily, variant: null };
    }

    const dot = rest.indexOf('.');
    if (dot === -1) {
        return null;
    }

    const family = rest.slice(0, dot);
    const variant = rest.slice(dot + 1);
    const canonicalFamily = [...AE2_CABLE_FAMILIES].find(
        (entry) => entry.toLowerCase() === family,
    );
    if (!canonicalFamily) {
        return null;
    }

    return { family: canonicalFamily, variant: variant || null };
};

const canonicalMaterialVariant = (variant: string): string => {
    for (const material of AE2_MATERIAL_VARIANTS) {
        if (variant.toLowerCase() === material.toLowerCase()) {
            return material;
        }
    }
    return variant;
};

const ae2CableVariantsCompatible = (
    requiredVariant: string | null,
    candidateVariant: string | null,
): boolean => {
    const required = requiredVariant ? canonicalMaterialVariant(requiredVariant) : null;
    const candidate = candidateVariant ? canonicalMaterialVariant(candidateVariant) : null;

    if (required === candidate) {
        return true;
    }
    if (required != null && candidate != null && required.toLowerCase() === candidate.toLowerCase()) {
        return true;
    }
    if (required == null) {
        return candidate != null && AE2_MATERIAL_VARIANTS.has(candidate);
    }
    if (candidate == null) {
        return AE2_MATERIAL_VARIANTS.has(required);
    }
    return false;
};

export const ae2ItemsCompatible = (requiredId: string, candidateId: string): boolean => {
    const required = ae2ItemFamilyParts(requiredId);
    const candidate = ae2ItemFamilyParts(candidateId);
    if (!required || !candidate || required.family !== candidate.family) {
        return false;
    }
    return ae2CableVariantsCompatible(required.variant, candidate.variant);
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

const metadataCompatible = (left?: number, right?: number): boolean => {
    if (left == null && right == null) {
        return true;
    }
    return (left ?? 0) === (right ?? 0);
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

    if (normalizedNeedle.includes(':') && normalizedId.includes(':')) {
        if (ae2ItemsCompatible(normalizedId, normalizedNeedle)) {
            return true;
        }
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
        return metadataCompatible(left.metadata, right.metadata);
    }

    if (left.itemId && right.itemId && ae2ItemsCompatible(left.itemId, right.itemId)) {
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
