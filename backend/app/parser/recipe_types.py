CRAFTING_SHAPED = "crafting_shaped"
CRAFTING_SHAPELESS = "crafting_shapeless"
SMELTING = "smelting"
BLASTING = "blasting"
SMOKING = "smoking"
CAMPFIRE_COOKING = "campfire_cooking"
STONECUTTING = "stonecutting"

SUPPORTED_RECIPE_TYPES: frozenset[str] = frozenset(
    {
        CRAFTING_SHAPED,
        CRAFTING_SHAPELESS,
        SMELTING,
        BLASTING,
        SMOKING,
        CAMPFIRE_COOKING,
        STONECUTTING,
    }
)

MACHINE_BY_TYPE: dict[str, str] = {
    CRAFTING_SHAPED: "minecraft:crafting_table",
    CRAFTING_SHAPELESS: "minecraft:crafting_table",
    SMELTING: "minecraft:furnace",
    BLASTING: "minecraft:blast_furnace",
    SMOKING: "minecraft:smoker",
    CAMPFIRE_COOKING: "minecraft:campfire",
    STONECUTTING: "minecraft:stonecutter",
}


def normalize_recipe_type(raw_type: str) -> str:
    """Map loader-specific type ids to canonical names (e.g. minecraft:crafting_shaped)."""
    if ":" not in raw_type:
        return raw_type

    namespace, name = raw_type.split(":", 1)
    if namespace in {"minecraft", "forge"}:
        return name
    return raw_type


def is_supported_recipe_type(raw_type: str) -> bool:
    return normalize_recipe_type(raw_type) in SUPPORTED_RECIPE_TYPES
