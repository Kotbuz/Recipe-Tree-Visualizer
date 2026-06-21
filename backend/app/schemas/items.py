from pydantic import BaseModel

from app.schemas.domain import Item, ModSummary, Recipe


class ModListResponse(BaseModel):
    mods: list[ModSummary]


class ItemSearchResponse(BaseModel):
    query: str
    items: list[Item]


class ItemRecipesResponse(BaseModel):
    item_id: str
    recipes: list[Recipe]
