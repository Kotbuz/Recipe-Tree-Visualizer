from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.recipes.ae2_material_metadata import _AE2_ITEM_MULTI_MATERIAL_METADATA
from app.recipes.loaders.ore_dict_loader import OreDictEntry, load_ore_dict

_CATALOG_FILE = "item_catalog.json"
_AE2_LANG_PATH = "assets/appliedenergistics2/lang/en_US.lang"
_ORE_LINE = re.compile(r"^ore=(?P<source>.+?)\s*->\s*(?P<target>\S+)")
_ORE_NAME_TO_ITEM_MATERIAL: dict[str, str] = {
    "crystalCertusQuartz": "CertusQuartzCrystal",
    "dustCertusQuartz": "CertusQuartzDust",
    "dustNetherQuartz": "NetherQuartzDust",
    "itemSilicon": "Silicon",
    "crystalFluix": "FluixCrystal",
    "dustFluix": "FluixDust",
    "pearlFluix": "FluixPearl",
    "crystalPureFluix": "PurifiedFluixCrystal",
    "dustWheat": "Flour",
    "dustIron": "IronDust",
    "dustGold": "GoldDust",
    "dustEnder": "EnderDust",
    "dustEnderPearl": "EnderDust",
}
_LANG_MATERIAL = re.compile(
    r"item\.appliedenergistics2\.ItemMaterial\.(\w+)\.name=(.+)"
)
_LANG_AE2_ENTRY = re.compile(
    r"(?:tile|item)\.appliedenergistics2\.([\w.]+)\.name=(.+)"
)
_BLOCK_SUBTYPE_METADATA = {
    "Block": 1,
    "Brick": 2,
    "SmallBrick": 3,
}
_AE2_CABLE_FAMILIES = frozenset(
    {"CableGlass", "CableCovered", "CableSmart", "CableDense", "CableAnchor"}
)
_AE2_MATERIAL_VARIANTS = frozenset({"Fluix", "Quartz"})
_AE2_PAINT_FAMILIES = {
    "PaintBall": "Paint Ball",
    "LumenPaintBall": "Lumen Paint Ball",
}


@dataclass(frozen=True)
class CatalogEntry:
    item_id: str
    metadata: int
    display_name: str
    icon_id: str
    mod_id: str | None = None


def catalog_path_for_version(version: str) -> Path:
    return get_settings().minecraft_versions_path / version / _CATALOG_FILE


@lru_cache(maxsize=8)
def load_item_catalog(version: str) -> dict[tuple[str, int], CatalogEntry]:
    path = catalog_path_for_version(version)
    if path.is_file():
        catalog = _load_catalog_file(path)
        if catalog:
            return catalog

    if version.startswith("1.7"):
        return _build_ae2_fallback_catalog(version)
    return {}


def resolve_catalog_entry(
    item_id: str,
    metadata: int | None,
    *,
    version: str,
) -> CatalogEntry | None:
    catalog = load_item_catalog(version)
    meta = 0 if metadata is None else metadata
    entry = catalog.get((item_id.strip().lower(), meta))
    if entry is None and meta != 0:
        entry = catalog.get((item_id.strip().lower(), 0))
    return entry


def resolve_catalog_display_name(
    item_id: str,
    metadata: int | None,
    *,
    version: str,
) -> str | None:
    entry = resolve_catalog_entry(item_id, metadata, version=version)
    if entry is not None:
        return entry.display_name
    return resolve_ae2_composite_display_name(item_id, version=version)


def resolve_ae2_composite_display_name(item_id: str, *, version: str) -> str | None:
    normalized = item_id.strip().lower()
    if not normalized.startswith("appliedenergistics2:item."):
        return None

    rest = item_id.split(":", 1)[1].removeprefix("item.")
    if "." not in rest:
        return None

    family, variant = rest.split(".", 1)
    flat, by_item = _parse_ae2_lang(version)
    variant_label = _humanize_material_name(variant)

    if family in _AE2_CABLE_FAMILIES:
        base_name = (
            flat.get(family)
            or by_item.get((f"appliedenergistics2:item.{family}", 0))
            or flat.get(f"ItemPart.{family}")
        )
        if base_name is None:
            base_name = _humanize_material_name(family)
        if variant in _AE2_MATERIAL_VARIANTS:
            return f"{variant_label} {base_name}"
        return f"{variant_label} {base_name}"

    if family in _AE2_PAINT_FAMILIES:
        base_name = flat.get("ItemPaintBall") or _AE2_PAINT_FAMILIES[family]
        return f"{variant_label} {base_name}"

    direct = by_item.get((f"appliedenergistics2:item.{rest}", 0))
    if direct is not None:
        return direct

    return None


def resolve_catalog_icon_id(
    item_id: str,
    metadata: int | None,
    *,
    version: str,
) -> str | None:
    entry = resolve_catalog_entry(item_id, metadata, version=version)
    if entry is not None:
        return entry.icon_id
    composite_name = resolve_ae2_composite_display_name(item_id, version=version)
    if composite_name is not None:
        return _icon_id_from_display_name(composite_name)
    return None


def _load_catalog_file(path: Path) -> dict[tuple[str, int], CatalogEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, list):
        return {}

    catalog: dict[tuple[str, int], CatalogEntry] = {}
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        item_id = raw.get("item")
        name = raw.get("name")
        if not isinstance(item_id, str) or not isinstance(name, str):
            continue
        metadata = raw.get("metadata", 0)
        if not isinstance(metadata, int):
            metadata = 0
        mod_id = raw.get("mod")
        icon_id = _icon_id_from_display_name(name)
        catalog[(item_id.strip().lower(), metadata)] = CatalogEntry(
            item_id=item_id,
            metadata=metadata,
            display_name=name,
            icon_id=icon_id,
            mod_id=mod_id if isinstance(mod_id, str) else None,
        )
    return catalog


def _build_ae2_fallback_catalog(version: str) -> dict[tuple[str, int], CatalogEntry]:
    catalog: dict[tuple[str, int], CatalogEntry] = {}
    ore_dict = load_ore_dict(version)
    material_names = _load_ae2_material_names(version)
    token_map = _build_ae2_token_map(version, ore_dict)

    for token, (item_id, metadata) in token_map.items():
        material_name = token.rsplit(":", 1)[-1].removeprefix("ItemMaterial.")
        display = material_names.get(material_name)
        if display is None:
            display = _humanize_material_name(material_name)
        meta = 0 if metadata is None else metadata
        catalog[(item_id.strip().lower(), meta)] = CatalogEntry(
            item_id=item_id,
            metadata=meta,
            display_name=display,
            icon_id=_icon_id_from_material_name(material_name),
            mod_id="appliedenergistics2",
        )

    for name, display in material_names.items():
        if name.startswith("Tool"):
            item_id = f"appliedenergistics2:item.{name}"
            catalog[(item_id.lower(), 0)] = CatalogEntry(
                item_id=item_id,
                metadata=0,
                display_name=display,
                icon_id=_icon_id_from_material_name(name),
                mod_id="appliedenergistics2",
            )

    for (item_id, metadata), display in _load_ae2_lang_display_names(version).items():
        catalog[(item_id.lower(), metadata)] = CatalogEntry(
            item_id=item_id,
            metadata=metadata,
            display_name=display,
            icon_id=_icon_id_from_display_name(display),
            mod_id="appliedenergistics2",
        )

    material_names = _load_ae2_material_names(version)
    for material_name, metadata in _AE2_ITEM_MULTI_MATERIAL_METADATA.items():
        if material_name == "InvalidType":
            continue
        display = material_names.get(material_name) or _humanize_material_name(material_name)
        item_id = "appliedenergistics2:item.ItemMultiMaterial"
        catalog[(item_id.lower(), metadata)] = CatalogEntry(
            item_id=item_id,
            metadata=metadata,
            display_name=display,
            icon_id=_icon_id_from_material_name(material_name),
            mod_id="appliedenergistics2",
        )

    for ore_name, entry in ore_dict.items():
        meta = 0 if entry.metadata is None else entry.metadata
        if entry.item_id.startswith("minecraft:"):
            from app.recipes.adapters import item_id_to_display_name

            display = item_id_to_display_name(entry.item_id)
        else:
            material_key = _guess_material_name_from_ore(ore_name)
            display = material_names.get(material_key)
            if display is None:
                display = _humanize_material_name(material_key)
        catalog[(entry.item_id.strip().lower(), meta)] = CatalogEntry(
            item_id=entry.item_id,
            metadata=meta,
            display_name=display,
            icon_id=_icon_id_from_display_name(display),
            mod_id=entry.item_id.split(":", 1)[0],
        )

    return catalog


def _build_ae2_token_map(
    version: str,
    ore_dict: dict[str, OreDictEntry],
) -> dict[str, tuple[str, int | None]]:
    tokens: dict[str, tuple[str, int | None]] = {}
    recipe_root = get_settings().minecraft_versions_path / version / "recipe" / "ae2-recipes"
    if not recipe_root.is_dir():
        return tokens

    for recipe_file in recipe_root.rglob("*.recipe"):
        for line in recipe_file.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _ORE_LINE.match(line.strip())
            if not match:
                continue
            source = match.group("source").strip()
            target = match.group("target").strip()
            entry = ore_dict.get(target)
            if entry is None:
                continue
            tokens[source] = (entry.item_id, entry.metadata)
            short_name = source.rsplit(":", 1)[-1]
            if short_name.startswith("ItemMaterial."):
                tokens[f"ae2:{short_name}"] = (entry.item_id, entry.metadata)
                tokens[f"appliedenergistics2:{short_name}"] = (entry.item_id, entry.metadata)

    for ore_name, material_name in _ORE_NAME_TO_ITEM_MATERIAL.items():
        entry = ore_dict.get(ore_name)
        if entry is None:
            continue
        meta = 0 if entry.metadata is None else entry.metadata
        for prefix in ("ae2", "appliedenergistics2"):
            tokens[f"{prefix}:ItemMaterial.{material_name}"] = (entry.item_id, meta)

    return tokens


def _load_ae2_material_names(version: str) -> dict[str, str]:
    flat, _ = _parse_ae2_lang(version)
    return flat


def _load_ae2_lang_display_names(version: str) -> dict[tuple[str, int], str]:
    _, by_item = _parse_ae2_lang(version)
    return by_item


@lru_cache(maxsize=8)
def _parse_ae2_lang(version: str) -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    mods_dir = get_settings().minecraft_versions_path / version / "mods"
    if not mods_dir.is_dir():
        return {}, {}

    import zipfile

    flat: dict[str, str] = {}
    by_item: dict[tuple[str, int], str] = {}
    for jar_path in sorted(mods_dir.glob("*appliedenergistics2*.jar")):
        try:
            with zipfile.ZipFile(jar_path) as archive:
                if _AE2_LANG_PATH not in archive.namelist():
                    continue
                text = archive.read(_AE2_LANG_PATH).decode("utf-8", errors="replace")
        except (OSError, zipfile.BadZipFile):
            continue

        for match in _LANG_MATERIAL.finditer(text):
            material_name = match.group(1)
            display = match.group(2).strip()
            flat[material_name] = display
            by_item[(f"appliedenergistics2:item.ItemMaterial.{material_name}", 0)] = display

        for match in _LANG_AE2_ENTRY.finditer(text):
            path = match.group(1)
            if path.startswith("ItemMaterial."):
                continue
            display = match.group(2).strip()
            item_id, metadata = _ae2_item_id_from_lang_path(path)
            by_item[(item_id, metadata)] = display
            _register_ae2_lang_aliases(flat, path, item_id, display)
        break

    return flat, by_item


def _ae2_item_id_from_lang_path(path: str) -> tuple[str, int]:
    parts = path.split(".")
    root = parts[0]
    if root.startswith("Block"):
        metadata = 0
        if len(parts) > 1:
            metadata = _BLOCK_SUBTYPE_METADATA.get(parts[1], 0)
        return f"appliedenergistics2:tile.{root}", metadata
    if path.startswith("ItemPart."):
        return f"appliedenergistics2:item.{path.removeprefix('ItemPart.')}", 0
    return f"appliedenergistics2:item.{path}", 0


def _register_ae2_lang_aliases(
    flat: dict[str, str],
    path: str,
    item_id: str,
    display: str,
) -> None:
    flat[path] = display
    short_name = item_id.rsplit(":", 1)[-1]
    if short_name.startswith("tile."):
        flat[short_name.removeprefix("tile.")] = display
    elif short_name.startswith("item."):
        flat[short_name.removeprefix("item.")] = display
    if path.startswith("ItemPart."):
        flat[path.removeprefix("ItemPart.")] = display
    if path == "ItemPaintBall":
        flat["PaintBall"] = display
        flat["LumenPaintBall"] = display.replace("Paint Ball", "Lumen Paint Ball")


def _guess_material_name_from_ore(ore_name: str) -> str:
    mapping = {
        "crystalCertusQuartz": "CertusQuartzCrystal",
        "dustCertusQuartz": "CertusQuartzDust",
        "crystalFluix": "FluixCrystal",
        "dustFluix": "FluixDust",
        "pearlFluix": "FluixPearl",
        "itemSilicon": "Silicon",
        "crystalPureFluix": "PurifiedFluixCrystal",
        "dustNetherQuartz": "NetherQuartzDust",
    }
    return mapping.get(ore_name, ore_name)


def _humanize_material_name(name: str) -> str:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return spaced.replace("_", " ").strip()


def _icon_id_from_material_name(material_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", material_name.lower()).strip("_")


def _icon_id_from_display_name(display_name: str) -> str:
    return display_name.strip().lower().replace(" ", "_")
