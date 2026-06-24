export interface RecipeItem {
    name: string;
    amount: number;
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
