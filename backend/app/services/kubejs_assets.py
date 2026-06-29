from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.version_service import version_service


@dataclass(frozen=True)
class KubejsAssetIndex:
    texture_paths: dict[str, Path]

    def resolve(self, lookup: str) -> Path | None:
        normalized = lookup.strip().lower().replace(" ", "_")
        if not normalized:
            return None

        candidates = _lookup_candidates(normalized)
        for candidate in candidates:
            path = self.texture_paths.get(candidate)
            if path is not None and path.is_file():
                return path
        return None


def resolve_kubejs_item_icon_path(
    version: str,
    filename: str,
    profile_id: str | None = None,
) -> Path | None:
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith(".png"):
        return None

    kubejs_dir = version_service.kubejs_dir(version, profile_id)
    if not kubejs_dir.is_dir():
        return None

    index = _build_kubejs_asset_index(kubejs_dir)
    stem = safe_name.removesuffix(".png").lower()
    return index.resolve(stem)


@lru_cache(maxsize=32)
def _build_kubejs_asset_index(kubejs_dir: str) -> KubejsAssetIndex:
    root = Path(kubejs_dir)
    texture_paths: dict[str, Path] = {}

    assets_dir = root / "assets"
    if assets_dir.is_dir():
        for png_path in assets_dir.rglob("*.png"):
            if not png_path.is_file():
                continue
            relative = png_path.relative_to(assets_dir)
            parts = relative.parts
            if len(parts) < 4 or parts[1] != "textures":
                continue
            namespace = parts[0]
            category = parts[2]
            stem = png_path.stem.lower()
            texture_paths[stem] = png_path
            texture_paths[f"{namespace}:{stem}"] = png_path
            texture_paths[f"{namespace}:textures/{category}/{stem}"] = png_path

    _index_custom_machinery(root, texture_paths)
    return KubejsAssetIndex(texture_paths=texture_paths)


def _index_custom_machinery(root: Path, texture_paths: dict[str, Path]) -> None:
    data_dir = root / "data"
    if not data_dir.is_dir():
        return

    for machine_file in sorted(data_dir.glob("*/machine/*.json")):
        if not machine_file.is_file():
            continue
        payload = _read_json(machine_file)
        if payload is None:
            continue

        block_id = _machine_block_id(payload)
        machine_name = machine_file.stem.lower()
        namespace = machine_file.relative_to(data_dir).parts[0]

        model_path = root / "assets" / namespace / "models" / "machine" / f"{machine_name}.json"
        front_texture = _machine_front_texture(model_path)
        if front_texture is None:
            continue

        png_path = _resolve_texture_reference(root, front_texture)
        if png_path is None:
            continue

        keys = {
            machine_name,
            f"{namespace}:{machine_name}",
            f"{namespace}:machine/{machine_name}",
        }
        if block_id:
            keys.add(block_id.lower())
            if ":" in block_id:
                keys.add(block_id.split(":", 1)[1].lower())

        for key in keys:
            texture_paths[key] = png_path


def _machine_block_id(payload: dict[str, object]) -> str | None:
    appearance = payload.get("appearance")
    if not isinstance(appearance, dict):
        return None
    for key in ("custommachinery:block", "block"):
        value = appearance.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _machine_front_texture(model_path: Path) -> str | None:
    payload = _read_json(model_path)
    if payload is None:
        return None
    textures = payload.get("textures")
    if not isinstance(textures, dict):
        return None
    front = textures.get("front")
    return front if isinstance(front, str) else None


def _resolve_texture_reference(root: Path, texture_ref: str) -> Path | None:
    if ":" not in texture_ref:
        return None
    namespace, path = texture_ref.split(":", 1)
    candidate = root / "assets" / namespace / "textures" / f"{path}.png"
    return candidate if candidate.is_file() else None


def _lookup_candidates(normalized: str) -> tuple[str, ...]:
    candidates = [normalized]
    if normalized.endswith("_front"):
        candidates.append(normalized.removesuffix("_front"))
    if normalized.endswith("_side"):
        candidates.append(normalized.removesuffix("_side"))
    if "/" in normalized:
        candidates.append(normalized.rsplit("/", 1)[-1])
    if ":" in normalized:
        candidates.append(normalized.split(":", 1)[1])
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def clear_kubejs_asset_index_cache() -> None:
    _build_kubejs_asset_index.cache_clear()
