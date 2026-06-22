from pydantic import BaseModel


class RecipeSummary(BaseModel):
    recipe_id: str
    machine_type: str
    machine_name: str
    inputs: list[str]
    outputs: list[str]


class RecipeListResponse(BaseModel):
    recipes: list[RecipeSummary]
