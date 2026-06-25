import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services.mod_service import mod_service
from app.services.vanilla_icon_service import vanilla_icon_service
from app.services.version_service import version_service


def _load_mods_on_startup() -> None:
    settings = get_settings()
    if not settings.mods_auto_load_on_startup:
        return

    default_version = version_service.resolve_default_version()
    if default_version is None:
        return

    summaries = mod_service.scan_storage_mods(default_version)
    if summaries:
        logger.info(
            "Loaded {} mod(s) for Minecraft {} ({} recipes total)",
            len(summaries),
            default_version,
            sum(summary.recipe_count for summary in summaries),
        )


async def _render_vanilla_icons_on_startup() -> None:
    settings = get_settings()
    if not settings.vanilla_icon_render_on_startup:
        return

    default_version = version_service.resolve_default_version()
    if default_version is None:
        return

    if version_service.resolve_jar_path(default_version) is None:
        return

    try:
        result = await asyncio.to_thread(vanilla_icon_service.ensure_icons, default_version)
        if result.errors:
            logger.warning(
                "Vanilla icon render for {} finished with errors: {}",
                default_version,
                "; ".join(result.errors),
            )
    except Exception:
        logger.exception("Failed to render vanilla icons for {}", default_version)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    logger.info(
        "Starting Recipe Tree Visualizer API on {}:{}", settings.api_host, settings.api_port
    )
    _load_mods_on_startup()
    render_task = asyncio.create_task(_render_vanilla_icons_on_startup())
    yield
    render_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await render_task
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
