export interface RecipeSummary {
    recipe_id: string;
    machine_type: string;
    machine_name: string;
    inputs: string[];
    outputs: string[];
}

export interface RecipeListResponse {
    recipes: RecipeSummary[];
}
