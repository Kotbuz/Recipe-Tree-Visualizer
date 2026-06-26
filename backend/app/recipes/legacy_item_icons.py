from __future__ import annotations

_DYE_ICON_BY_METADATA: dict[int, str] = {
    0: "ink_sac",
    1: "red_dye",
    2: "green_dye",
    3: "cocoa_beans",
    4: "lapis_lazuli",
    5: "purple_dye",
    6: "cyan_dye",
    7: "light_gray_dye",
    8: "gray_dye",
    9: "pink_dye",
    10: "lime_dye",
    11: "yellow_dye",
    12: "light_blue_dye",
    13: "magenta_dye",
    14: "orange_dye",
    15: "bone_meal",
}

_WOOL_ICON_BY_METADATA: dict[int, str] = {
    0: "white_wool",
    1: "orange_wool",
    2: "magenta_wool",
    3: "light_blue_wool",
    4: "yellow_wool",
    5: "lime_wool",
    6: "pink_wool",
    7: "gray_wool",
    8: "light_gray_wool",
    9: "cyan_wool",
    10: "purple_wool",
    11: "blue_wool",
    12: "brown_wool",
    13: "green_wool",
    14: "red_wool",
    15: "black_wool",
}

_WOOD_ICON_BY_METADATA: dict[int, str] = {
    0: "oak",
    1: "spruce",
    2: "birch",
    3: "jungle",
    4: "acacia",
    5: "dark_oak",
}

_LEGACY_ITEM_METADATA: dict[str, dict[int, str]] = {
    "minecraft:dye": _DYE_ICON_BY_METADATA,
    "minecraft:wool": _WOOL_ICON_BY_METADATA,
    "minecraft:cloth": _WOOL_ICON_BY_METADATA,
    "minecraft:log": {meta: f"{wood}_log" for meta, wood in _WOOD_ICON_BY_METADATA.items()},
    "minecraft:log2": {
        0: "acacia_log",
        1: "dark_oak_log",
    },
    "minecraft:planks": {meta: f"{wood}_planks" for meta, wood in _WOOD_ICON_BY_METADATA.items()},
    "minecraft:leaves": {meta: f"{wood}_leaves" for meta, wood in _WOOD_ICON_BY_METADATA.items()},
    "minecraft:leaves2": {
        0: "acacia_leaves",
        1: "dark_oak_leaves",
    },
    "minecraft:sapling": {meta: f"{wood}_sapling" for meta, wood in _WOOD_ICON_BY_METADATA.items()},
    "minecraft:stone": {
        0: "stone",
        1: "granite",
        2: "polished_granite",
        3: "diorite",
        4: "polished_diorite",
        5: "andesite",
        6: "polished_andesite",
    },
    "minecraft:stonebrick": {
        0: "stone_bricks",
        1: "mossy_stone_bricks",
        2: "cracked_stone_bricks",
        3: "chiseled_stone_bricks",
    },
    "minecraft:monster_egg": {
        0: "stone",
        1: "cobblestone",
        2: "stone_bricks",
    },
    "minecraft:coal": {
        0: "coal",
        1: "charcoal",
    },
    "minecraft:stained_hardened_clay": {
        meta: f"{_WOOL_ICON_BY_METADATA[meta].removesuffix('_wool')}_terracotta"
        for meta in _WOOL_ICON_BY_METADATA
    },
    "minecraft:carpet": {
        meta: f"{_WOOL_ICON_BY_METADATA[meta].removesuffix('_wool')}_carpet"
        for meta in _WOOL_ICON_BY_METADATA
    },
    "minecraft:stained_glass": {
        meta: f"{_WOOL_ICON_BY_METADATA[meta].removesuffix('_wool')}_stained_glass"
        for meta in _WOOL_ICON_BY_METADATA
    },
    "minecraft:stained_glass_pane": {
        meta: f"{_WOOL_ICON_BY_METADATA[meta].removesuffix('_wool')}_stained_glass_pane"
        for meta in _WOOL_ICON_BY_METADATA
    },
}

_LEGACY_ITEM_ALIASES: dict[str, str] = {
    "minecraft:fire": "iron_ingot",
}


def resolve_legacy_icon_id(
    item_id: str,
    metadata: int | None,
    *,
    version: str,
) -> str | None:
    if not version.startswith("1.7"):
        return None

    normalized = item_id.strip().lower()
    if metadata is None:
        return _LEGACY_ITEM_ALIASES.get(normalized)

    table = _LEGACY_ITEM_METADATA.get(normalized)
    if table is not None:
        return table.get(metadata)

    return None


def resolve_legacy_display_name(
    item_id: str,
    metadata: int | None,
    *,
    version: str,
) -> str | None:
    icon_id = resolve_legacy_icon_id(item_id, metadata, version=version)
    if icon_id is None:
        return None
    return icon_id.replace("_", " ")
