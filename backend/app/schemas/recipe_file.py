from pydantic import BaseModel


class RecipeItem(BaseModel):
    name: str
    amount: int = 1
    item_id: str | None = None
    icon_id: str | None = None
    metadata: int | None = None


class RecipeSummary(BaseModel):
    recipe_id: str
    machine_type: str
    machine_name: str
    inputs: list[RecipeItem]
    outputs: list[RecipeItem]


class RecipeListResponse(BaseModel):
    recipes: list[RecipeSummary]
