from fastapi import APIRouter

from app.api.routes import graph, health, items, mods, recipes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(mods.router)
api_router.include_router(items.router)
api_router.include_router(graph.router)
api_router.include_router(recipes.router)
