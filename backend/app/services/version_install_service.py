from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

from app.services.minecraft_version_catalog import get_minecraft_version_catalog
from app.services.vanilla_icon_service import vanilla_icon_service
from app.services.version_service import version_service


@dataclass(frozen=True)
class VersionInstallResult:
    version: str
    client_jar_path: str
    icons_rendered: int
    icon_errors: tuple[str, ...]


class VersionInstallService:
    def install(self, version: str) -> VersionInstallResult:
        normalized = version.strip()
        if not normalized:
            raise ValueError("Version is required")

        entry = get_minecraft_version_catalog().get_release(normalized)
        if entry is None:
            raise ValueError(f"Release version not found in catalog: {normalized}")

        version_service.ensure_version_layout(normalized)
        client_jar = version_service.client_jar_path(normalized)
        self._download_file(entry.client_url, client_jar)

        logger.info("Installed Minecraft {} at {}", normalized, client_jar)
        render_result = vanilla_icon_service.ensure_icons(normalized)

        return VersionInstallResult(
            version=normalized,
            client_jar_path=str(client_jar),
            icons_rendered=render_result.rendered,
            icon_errors=tuple(render_result.errors),
        )

    @staticmethod
    def _download_file(url: str, destination) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with (
            httpx.Client(timeout=600.0, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            destination.write_bytes(response.read())


version_install_service = VersionInstallService()
