from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.recipes.loaders.tag_loader import TagLoader, normalize_tag_id


@dataclass(frozen=True)
class OreDictEntry:
    item_id: str
    metadata: int | None = None


@lru_cache
def _ore_dict_path(version: str) -> Path:
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / "data" / "ore_dict" / f"{version}.json"


def load_ore_dict(version: str) -> dict[str, OreDictEntry]:
    path = _ore_dict_path(version)
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    entries: dict[str, OreDictEntry] = {}
    for ore_name, raw_value in payload.items():
        if not isinstance(ore_name, str):
            continue
        entry = _parse_ore_dict_value(raw_value)
        if entry is not None:
            entries[ore_name] = entry
    return entries


def _parse_ore_dict_value(raw_value: object) -> OreDictEntry | None:
    if isinstance(raw_value, str):
        return OreDictEntry(item_id=raw_value)

    if isinstance(raw_value, list) and raw_value:
        return _parse_ore_dict_value(raw_value[0])

    if isinstance(raw_value, dict):
        item_id = raw_value.get("item") or raw_value.get("id")
        if not isinstance(item_id, str):
            return None
        metadata = raw_value.get("metadata", raw_value.get("data"))
        if metadata is not None and not isinstance(metadata, int):
            return None
        return OreDictEntry(item_id=item_id, metadata=metadata)

    return None
