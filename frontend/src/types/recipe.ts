export interface RecipeItem {
    name: string;
    amount: number;
    item_id?: string;
}

export interface RecipeSummary {
    recipe_id: string;
    machine_type: string;
    machine_name: string;
    inputs: RecipeItem[];
    outputs: RecipeItem[];
}

export interface RecipeListResponse {
    recipes: RecipeSummary[];
}

export type NodeKind = 'recipe' | 'chest' | 'outpost';

export type SlotType = 'input' | 'output';

export interface NodeSlot {
    nodeId: string;
    slotType: SlotType;
    itemIndex: number;
    itemName: string;
}

export interface RecipeConnection {
    id: string;
    from: NodeSlot;
    to: NodeSlot;
}

/** Сопоставление предмета с тегом Minecraft (planks) и конкретным видом (oak planks). */
export const itemsMatch = (requiredName: string, candidateName: string): boolean => {
    if (!requiredName || !candidateName) return false;

    const required = requiredName.toLowerCase();
    const candidate = candidateName.toLowerCase();

    if (required === candidate) return true;
    if (candidate.endsWith(` ${required}`)) return true;
    if (required.endsWith(` ${candidate}`)) return true;

    return false;
};
