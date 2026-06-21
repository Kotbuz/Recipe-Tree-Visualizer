from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    logger.info(
        "Starting Recipe Tree Visualizer API on {}:{}", settings.api_host, settings.api_port
    )
    yield
    logger.info("Shutting down Recipe Tree Visualizer API")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Recipe Tree Visualizer API",
        description="Extract Minecraft mod recipes and build craft dependency trees.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
