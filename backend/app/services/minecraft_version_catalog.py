from __future__ import annotations

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from app.core.config import get_settings

GIST_RAW_URL = (
    "https://gist.githubusercontent.com/cliffano/"
    "77a982a7503669c3e1acb0a0cf6127e9/raw/minecraft-server-jar-downloads.md"
)

_TABLE_ROW = re.compile(
    r"^\|\s*(?P<version>[^|]+?)\s*\|\s*"
    r"(?P<server><https?://[^>|]+>)\s*\|\s*"
    r"(?P<client><https?://[^>|]+>)\s*\|\s*$"
)
_URL_IN_ANGLE = re.compile(r"<(https?://[^>]+)>")
_PRERELEASE_MARKERS = (
  "snapshot",
  "-pre-",
  "-rc-",
  "-inf-",
  "experimental",
  "combat-test",
)


@dataclass(frozen=True)
class VersionCatalogEntry:
    version: str
    client_url: str
    server_url: str


def is_release_version(version: str) -> bool:
    normalized = version.strip().lower()
    if not normalized or normalized == "minecraft version":
        return False
    return not any(marker in normalized for marker in _PRERELEASE_MARKERS)


def parse_catalog_markdown(markdown: str) -> list[VersionCatalogEntry]:
    entries: list[VersionCatalogEntry] = []
    seen: set[str] = set()

    for line in markdown.splitlines():
        match = _TABLE_ROW.match(line.strip())
        if not match:
            continue

        version = match.group("version").strip()
        if not is_release_version(version):
            continue

        server_match = _URL_IN_ANGLE.search(match.group("server"))
        client_match = _URL_IN_ANGLE.search(match.group("client"))
        if server_match is None or client_match is None:
            continue

        if version in seen:
            continue
        seen.add(version)
        entries.append(
            VersionCatalogEntry(
                version=version,
                client_url=client_match.group(1),
                server_url=server_match.group(1),
            )
        )

    return entries


class MinecraftVersionCatalog:
    def __init__(self) -> None:
        self._settings = get_settings()

    def list_releases(self, *, force_refresh: bool = False) -> list[VersionCatalogEntry]:
        if not force_refresh:
            cached = self._read_cache()
            if cached is not None:
                return cached

        markdown = self._fetch_markdown()
        entries = parse_catalog_markdown(markdown)
        self._write_cache(markdown)
        return entries

    def get_release(self, version: str) -> VersionCatalogEntry | None:
        needle = version.strip()
        for entry in self.list_releases():
            if entry.version == needle:
                return entry
        return None

    def _cache_path(self) -> Path:
        cache_dir = self._settings.minecraft_versions_path / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "version-catalog.md"

    def _read_cache(self) -> list[VersionCatalogEntry] | None:
        cache_path = self._cache_path()
        if not cache_path.is_file():
            return None

        age_seconds = time.time() - cache_path.stat().st_mtime
        if age_seconds > self._settings.version_catalog_cache_ttl_seconds:
            return None

        return parse_catalog_markdown(cache_path.read_text(encoding="utf-8"))

    def _write_cache(self, markdown: str) -> None:
        self._cache_path().write_text(markdown, encoding="utf-8")

    @staticmethod
    def _fetch_markdown() -> str:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(GIST_RAW_URL)
            response.raise_for_status()
            return response.text


@lru_cache
def get_minecraft_version_catalog() -> MinecraftVersionCatalog:
    return MinecraftVersionCatalog()
