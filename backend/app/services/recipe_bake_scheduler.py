from __future__ import annotations

import threading

from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version


def schedule_neo_recipe_bake_after_import(
    version: str,
    profile_id: str,
    *,
    source_path: str,
    minecraft_version: str,
) -> bool:
    """Запускает in-game export в фоне (HTTP к recipe-exporter-neo)."""
    settings = get_settings()
    if not settings.auto_bake_recipes_after_instance_import:
        return False
    if not settings.neo_recipe_exporter_url.strip():
        logger.info(
            "Auto recipe bake skipped for {}::{}: NEO_RECIPE_EXPORTER_URL is empty",
            version,
            profile_id,
        )
        return False
    if recipe_layout_for_version(minecraft_version) == "jvm":
        logger.info(
            "Auto recipe bake skipped for {}: JVM layout uses legacy exporter",
            minecraft_version,
        )
        return False

    def _run() -> None:
        from app.services.neo_recipe_export_service import neo_recipe_export_service

        logger.info(
            "Starting background neo recipe bake for {}::{}",
            version,
            profile_id,
        )
        try:
            result = neo_recipe_export_service.bake_profile(
                version,
                profile_id,
                force=True,
                source_path_override=source_path,
            )
            if result.get("status") == "ok":
                logger.info(
                    "Background neo recipe bake finished: {} recipes",
                    result.get("recipe_count"),
                )
            else:
                logger.warning(
                    "Background neo recipe bake failed for {}::{}: {}",
                    version,
                    profile_id,
                    result.get("error"),
                )
        except Exception as exc:
            logger.exception(
                "Background neo recipe bake crashed for {}::{}: {}",
                version,
                profile_id,
                exc,
            )

    thread = threading.Thread(
        target=_run,
        name=f"neo-recipe-bake-{profile_id}",
        daemon=True,
    )
    thread.start()
    return True
