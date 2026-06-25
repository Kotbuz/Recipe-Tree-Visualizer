from pydantic import BaseModel

from app.schemas.domain import Item, ModSummary
from app.schemas.recipe_file import RecipeSummary


class ModListResponse(BaseModel):
    mods: list[ModSummary]


class ItemSearchResponse(BaseModel):
    query: str
    items: list[Item]


class ItemRecipesResponse(BaseModel):
    item_id: str
    recipes: list[RecipeSummary]
