from fastapi import APIRouter, Query

from app.schemas.recipe_file import RecipeListResponse
from app.services.recipe_service import recipe_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=RecipeListResponse)
def list_recipes(version: str = Query(default="26.2")) -> RecipeListResponse:
    return RecipeListResponse(recipes=recipe_service.list_recipes(version))
