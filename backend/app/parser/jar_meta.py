from __future__ import annotations

from pathlib import Path

_JAR_MOD_ID_HINTS: tuple[tuple[str, str], ...] = (
    ("appliedenergistics2", "appliedenergistics2"),
    ("ic2classic", "ic2"),
    ("ic2-classic", "ic2"),
    ("industrialcraft", "ic2"),
    ("forgemultipart", "forgemultipart"),
    ("mekanism", "mekanism"),
    ("thaumcraft", "thaumcraft"),
    ("buildcraft", "buildcraft"),
    ("thermal", "thermalfoundation"),
    ("cofh", "cofhcore"),
    ("codechickencore", "codechickencore"),
    ("codechickenlib", "codechickenlib"),
)


def guess_mod_id_from_jar_filename(jar_name: str) -> str:
    lowered = jar_name.lower()
    for needle, mod_id in _JAR_MOD_ID_HINTS:
        if needle in lowered:
            return mod_id
    stem = Path(jar_name).stem.lower()
    return stem.split("-", 1)[0]


def guess_display_name_from_jar_filename(jar_name: str, mod_id: str) -> str:
    lowered = jar_name.lower()
    if "ic2classic" in lowered or "ic2-classic" in lowered:
        return "IC2 Classic"
    if mod_id == "ic2":
        return "IndustrialCraft 2"
    stem = Path(jar_name).stem
    return stem.split("-", 1)[0]
