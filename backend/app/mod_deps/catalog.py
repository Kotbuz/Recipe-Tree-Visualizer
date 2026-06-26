from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class DependencyCatalogEntry:
    dependency_name: str
    modrinth_slug: str | None = None
    curseforge_slug: str | None = None
    curseforge_project_id: int | None = None
    search_terms: tuple[str, ...] = ()
    file_name_contains: tuple[str, ...] = ()


@lru_cache
def _catalog_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "mod_dependencies"


def load_dependency_catalog(version: str) -> dict[str, DependencyCatalogEntry]:
    path = _catalog_dir() / f"{version}.json"
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    entries: dict[str, DependencyCatalogEntry] = {}
    for name, raw in payload.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            continue
        entries[name] = DependencyCatalogEntry(
            dependency_name=name,
            modrinth_slug=_optional_str(raw.get("modrinth_slug")),
            curseforge_slug=_optional_str(raw.get("curseforge_slug")),
            curseforge_project_id=_optional_int(raw.get("curseforge_project_id")),
            search_terms=_optional_str_list(raw.get("search_terms")),
            file_name_contains=_optional_str_list(raw.get("file_name_contains")),
        )
    return entries


def catalog_entry_for(
    catalog: dict[str, DependencyCatalogEntry],
    dependency_name: str,
) -> DependencyCatalogEntry:
    if dependency_name in catalog:
        return catalog[dependency_name]

    for key, entry in catalog.items():
        if key.lower() == dependency_name.lower():
            return entry

    return DependencyCatalogEntry(
        dependency_name=dependency_name,
        search_terms=(dependency_name,),
    )


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _optional_str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())
