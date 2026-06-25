from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

from app.core.config import get_settings
from app.services.recipe_service import recipe_service
from app.services.version_service import item_name_to_texture_id, version_service


@dataclass(frozen=True)
class VanillaIconRenderResult:
    version: str
    required: int
    already_present: int
    requested: int
    rendered: int
    skipped: int
    errors: list[str]


class VanillaIconService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def collect_required_icon_ids(self, version: str) -> list[str]:
        icon_ids: set[str] = set()
        for recipe in recipe_service.get_recipes(version):
            for item in recipe.inputs + recipe.outputs:
                icon_ids.add(item_name_to_texture_id(item.name))
        return sorted(icon_ids)

    def ensure_icons(self, version: str) -> VanillaIconRenderResult:
        jar_path = version_service.resolve_jar_path(version)
        if jar_path is None:
            logger.warning("Vanilla jar not found for version {}", version)
            return VanillaIconRenderResult(
                version=version,
                required=0,
                already_present=0,
                requested=0,
                rendered=0,
                skipped=0,
                errors=[f"Jar not found for version {version}"],
            )

        required_ids = self.collect_required_icon_ids(version)
        version_service.ensure_rendered_icons_dir(version)
        existing_ids = version_service.list_rendered_icon_ids(version)
        missing_ids = [icon_id for icon_id in required_ids if icon_id not in existing_ids]

        if not missing_ids:
            logger.info(
                "Vanilla icons up to date for {} ({} icons)",
                version,
                len(existing_ids),
            )
            return VanillaIconRenderResult(
                version=version,
                required=len(required_ids),
                already_present=len(existing_ids),
                requested=0,
                rendered=0,
                skipped=0,
                errors=[],
            )

        renderer_jar = version_service.renderer_jar_path(version)
        output_dir = version_service.renderer_output_dir(version)
        if renderer_jar is None:
            return VanillaIconRenderResult(
                version=version,
                required=len(required_ids),
                already_present=len(existing_ids),
                requested=len(missing_ids),
                rendered=0,
                skipped=0,
                errors=["Could not map jar path for renderer"],
            )

        rendered_total = 0
        skipped_total = 0
        errors: list[str] = []
        batch_size = self._settings.renderer_batch_size

        for offset in range(0, len(missing_ids), batch_size):
            batch = missing_ids[offset : offset + batch_size]
            try:
                payload = self._render_batch(renderer_jar, output_dir, batch, version)
            except httpx.HTTPError as exc:
                message = f"Renderer request failed: {exc}"
                logger.error(message)
                errors.append(message)
                break

            rendered_total += len(payload.get("rendered", []))
            skipped_total += len(payload.get("skipped", []))
            if payload.get("status") == "error":
                errors.append(str(payload.get("error", "Unknown renderer error")))

        logger.info(
            "Vanilla icon render for {}: rendered={}, skipped={}, missing={}",
            version,
            rendered_total,
            skipped_total,
            len(missing_ids),
        )

        return VanillaIconRenderResult(
            version=version,
            required=len(required_ids),
            already_present=len(existing_ids),
            requested=len(missing_ids),
            rendered=rendered_total,
            skipped=skipped_total,
            errors=errors,
        )

    def _render_batch(
        self,
        jar_path: str,
        output_dir: str,
        icon_ids: list[str],
        version: str,
    ) -> dict[str, object]:
        body = {
            "jar_path": jar_path,
            "output_dir": output_dir,
            "filter": icon_ids,
            "width": self._settings.renderer_icon_size,
            "height": self._settings.renderer_icon_size,
            "no_animation": True,
            "minecraft_version": self._settings.minecraft_render_version,
        }
        url = f"{self._settings.renderer_url.rstrip('/')}/render"
        timeout = httpx.Timeout(self._settings.renderer_timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise httpx.HTTPError("Renderer returned non-object JSON")
            return payload


vanilla_icon_service = VanillaIconService()
