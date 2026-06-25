from fastapi import APIRouter, Query

from app.recipes.focus import RecipeIngredientRole
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
    focus_item: str | None = Query(default=None, min_length=1),
    focus_role: RecipeIngredientRole | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    include_mods: bool = Query(default=True),
) -> RecipeListResponse:
    recipes = recipe_service.search_recipes(
        version=version,
        query=q,
        uses_item=uses_item,
        produces_item=produces_item,
        focus_item=focus_item,
        focus_role=focus_role.value if focus_role is not None else None,
        limit=limit,
        include_mods=include_mods,
    )
    return RecipeListResponse(recipes=recipes)
