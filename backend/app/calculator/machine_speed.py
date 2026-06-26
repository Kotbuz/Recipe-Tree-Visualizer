"""Machine throughput multipliers relative to base recipe duration."""

from __future__ import annotations

_DEFAULT_SPEED = 1.0

# Vanilla smelting durations already differ per recipe type (smelting vs blasting).
# Speed multipliers apply when the same recipe runs on a faster machine (often modded).
_MACHINE_SPEED: dict[str, float] = {
    "minecraft:crafting_table": 1.0,
    "minecraft:furnace": 1.0,
    "minecraft:blast_furnace": 1.0,
    "minecraft:smoker": 1.0,
    "minecraft:campfire": 1.0,
    "minecraft:stonecutter": 1.0,
    "minecraft:brewing_stand": 1.0,
    "minecraft:composter": 1.0,
    "minecraft:anvil": 1.0,
}


def machine_speed(catalyst_id: str) -> float:
    return _MACHINE_SPEED.get(catalyst_id, _DEFAULT_SPEED)
