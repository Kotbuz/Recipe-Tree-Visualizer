from fastapi import APIRouter

from app.api.routes import graph, health, items, modpack, mods, profiles, recipes, settings, versions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(mods.router)
api_router.include_router(items.router)
api_router.include_router(graph.router)
api_router.include_router(recipes.router)
api_router.include_router(versions.router)
api_router.include_router(modpack.router)
api_router.include_router(profiles.router)
api_router.include_router(settings.router)
