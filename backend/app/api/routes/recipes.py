from fastapi import APIRouter, Query

from app.schemas.recipe_file import RecipeListResponse
from app.services.recipe_service import recipe_service

router = APIRouter(prefix="/recipes", tags=["recipes"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 50


@router.get("", response_model=RecipeListResponse)
@router.get("/", response_model=RecipeListResponse, include_in_schema=False)
def search_recipes(
    version: str = Query(default="26.2"),
    q: str | None = Query(default=None, min_length=1),
    uses_item: str | None = Query(default=None, min_length=1),
    produces_item: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> RecipeListResponse:
    recipes = recipe_service.search_recipes(
        version=version,
        query=q,
        uses_item=uses_item,
        produces_item=produces_item,
        limit=limit,
    )
    return RecipeListResponse(recipes=recipes)
