from fastapi import APIRouter, Query

from app.schemas.items import ItemRecipesResponse, ItemSearchResponse
from app.services.graph_service import graph_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/search", response_model=ItemSearchResponse)
def search_items(
    q: str = Query(min_length=1), limit: int = Query(default=20, ge=1, le=100)
) -> ItemSearchResponse:
    return graph_service.search_items(q, limit)


@router.get("/{item_id}/recipes", response_model=ItemRecipesResponse)
def get_item_recipes(item_id: str) -> ItemRecipesResponse:
    return graph_service.get_item_recipes(item_id)
