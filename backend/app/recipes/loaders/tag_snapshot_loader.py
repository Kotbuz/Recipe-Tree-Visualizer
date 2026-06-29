from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.recipes.loaders.tag_loader import TagLoader, normalize_tag_id

_MOD_MATERIAL_PREFIXES: frozenset[str] = frozenset(
    {
        "alltheores",
        "mekanism",
        "actuallyadditions",
        "immersiveengineering",
        "ae2",
        "appliedenergistics2",
        "create",
        "thermal",
        "enderio",
        "techopolis",
    }
)


_CATEGORY_LABELS: dict[str, str] = {
    "dusts": "dust",
    "gems": "",
    "gears": "gear",
    "rods": "rod",
    "plates": "plate",
    "ingots": "ingot",
    "nuggets": "nugget",
    "ores": "ore",
    "raw_materials": "raw",
    "storage_blocks": "block",
    "glass_blocks": "glass block",
    "blocks": "block",
    "leathers": "leather",
    "wires": "wire",
    "coins": "coin",
}


def common_tag_display_name(tag_id: str) -> str | None:
    normalized = normalize_tag_id(tag_id)
    if not normalized.startswith("tag:c:"):
        return None

    path = normalized.removeprefix("tag:c:")
    segments = [part.replace("_", " ") for part in path.split("/") if part]
    if not segments:
        return None

    if len(segments) == 1:
        return segments[0].title()

    category = path.split("/", 1)[0]
    material = _humanize_tag_material(segments[-1])
    material_title = material.title()

    if category == "glass_blocks" and material == "cheap":
        return "Cheap Glass Block"
    if category == "glass_blocks":
        return f"{material_title} Glass Block"

    suffix = _CATEGORY_LABELS.get(category)
    if suffix is not None:
        if suffix and material_title.lower().endswith(f" {suffix}"):
            return material_title
        if suffix:
            return f"{material_title} {suffix.title()}"
        return material_title

    if len(segments) == 2:
        return f"{material_title} ({segments[0].title()})"

    return " / ".join(segment.title() for segment in segments)


def common_tag_aliases(tag_id: str) -> dict[str, str]:
    display = common_tag_display_name(tag_id)
    if display is None:
        return {}

    aliases: dict[str, str] = {}
    normalized = normalize_tag_id(tag_id)
    path = normalized.removeprefix("tag:c:")
    segments = path.split("/")

    aliases[display.lower()] = display
    aliases[path.lower()] = display
    aliases[path.replace("/", " ").lower()] = display

    if len(segments) >= 2:
        material = _humanize_tag_material(segments[-1])
        category = segments[0].replace("_", " ")
        aliases[f"{category} {material}".lower()] = display
        aliases[f"{material} {category}".lower()] = display
        if " " in material or "_" in segments[-1]:
            aliases[material.lower()] = display

    return aliases


def _humanize_tag_material(raw_material: str) -> str:
    parts = [part for part in raw_material.replace("_", " ").split() if part]
    if len(parts) >= 2 and parts[0].lower() in _MOD_MATERIAL_PREFIXES:
        parts = parts[1:]
    return " ".join(parts)


@lru_cache
def _bundled_snapshot_path(version: str) -> Path:
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / "data" / "tag_snapshots" / f"{version}.json"


def version_tag_snapshot_path(version: str) -> Path:
    from app.core.config import get_settings

    return get_settings().minecraft_versions_path / version / "tag_snapshot.json"


def load_tag_snapshot(version: str) -> dict[str, frozenset[str]]:
    for path in (version_tag_snapshot_path(version), _bundled_snapshot_path(version)):
        if not path.is_file():
            continue
        snapshot = _load_tag_snapshot_file(path)
        if snapshot:
            return snapshot
    return {}


def _load_tag_snapshot_file(path: Path) -> dict[str, frozenset[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    members: dict[str, frozenset[str]] = {}
    for tag_id, raw_members in payload.items():
        if not isinstance(tag_id, str) or not isinstance(raw_members, list):
            continue
        item_ids = {
            item_id
            for item_id in raw_members
            if isinstance(item_id, str) and item_id and not item_id.startswith("#")
        }
        if item_ids:
            members[normalize_tag_id(tag_id)] = frozenset(item_ids)
    return members


def merge_snapshot_aliases(registry_aliases: dict[str, str], version: str) -> None:
    snapshot = load_tag_snapshot(version)
    for tag_id in snapshot:
        for alias_key, alias_value in common_tag_aliases(tag_id).items():
            registry_aliases.setdefault(alias_key, alias_value)
