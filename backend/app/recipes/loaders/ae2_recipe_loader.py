from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.parser.recipe_types import CRAFTING_SHAPED, CRAFTING_SHAPELESS, SMELTING
from app.recipes.ae2_material_metadata import ae2_item_material_metadata
from app.recipes.loaders.item_catalog_loader import _build_ae2_token_map
from app.recipes.loaders.ore_dict_loader import OreDictEntry, load_ore_dict
from app.recipes.item_ref import split_trailing_metadata
from app.recipes.models import ProviderResult, Recipe, RecipeIO, SkippedRecipe
from app.recipes.recipe_io_utils import normalize_recipe
from app.recipes.types import RecipeType

_RECIPE_BLOCK_START = re.compile(r"^(?P<type>shaped|shapeless|press|inscribe)=$")
_INLINE_RECIPE = re.compile(r"^(?P<type>\w+)=\s*(?P<body>.+)$")
_OUTPUT_LINE = re.compile(r"^->\s*(?P<output>.+)$")
_ORE_LINE = re.compile(r"^ore=(?P<source>.+?)\s*->\s*(?P<target>\S+)")
_GROUP_LINE = re.compile(r"^group=(?P<options>.+?)\s*->\s*(?P<alias>\S+)")
_ALIAS_LINE = re.compile(r"^alias=(?P<from>\S+)\s*->\s*(?P<to>\S+)")
_MULTILINE_BLOCK_TYPES = frozenset({"shaped", "shapeless", "press", "inscribe"})
_AE2_MACHINE_CONFIG: dict[str, tuple[RecipeType, str, str]] = {
    "smelt": (RecipeType.SMELTING, SMELTING, "minecraft:furnace"),
    "grind": (RecipeType.SMELTING, "ae2:grind", "appliedenergistics2:tile.BlockGrinder"),
    "grindfz": (RecipeType.SMELTING, "ae2:grind", "appliedenergistics2:tile.BlockGrinder"),
    "press": (RecipeType.CRAFTING_SHAPELESS, "ae2:press", "appliedenergistics2:tile.BlockInscriber"),
    "inscribe": (RecipeType.CRAFTING_SHAPELESS, "ae2:inscribe", "appliedenergistics2:tile.BlockInscriber"),
    "macerator": (RecipeType.SMELTING, "ae2:macerator", "ic2:blockMachine"),
    "pulverizer": (RecipeType.SMELTING, "ae2:pulverizer", "thermalexpansion:Machine"),
    "mekcrusher": (RecipeType.SMELTING, "ae2:mekcrusher", "mekanism:MachineBlock"),
    "mekechamber": (RecipeType.SMELTING, "ae2:mekechamber", "mekanism:MachineBlock"),
    "hccrusher": (RecipeType.SMELTING, "ae2:hccrusher", "hydraulicraft:hcMachine"),
    "crusher": (RecipeType.SMELTING, "ae2:crusher", "rotarycraft:machine"),
}


@dataclass
class _Ae2RecipeContext:
    version: str
    ore_dict: dict[str, OreDictEntry]
    ore_to_ae2: dict[str, str] = field(default_factory=dict)
    groups: dict[str, list[str]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    ae2_tokens: dict[str, tuple[str, int | None]] = field(default_factory=dict)


def load_ae2_recipe_directory(recipe_root: Path, *, version: str) -> ProviderResult:
    if not recipe_root.is_dir():
        return ProviderResult()

    context = _build_context(recipe_root, version)
    result = ProviderResult()

    for recipe_file in sorted(recipe_root.rglob("*.recipe")):
        if recipe_file.name in {"index.recipe", "README.html"}:
            continue
        text = recipe_file.read_text(encoding="utf-8", errors="replace")
        relative = recipe_file.relative_to(recipe_root).as_posix()
        for block_type, lines, recipe_index in _iter_recipe_definitions(text):
            recipe_id = f"appliedenergistics2:ae2/{relative}/{recipe_index}"
            try:
                recipe = _parse_block(block_type, lines, recipe_id, context)
            except ValueError as exc:
                result.skipped.append(
                    SkippedRecipe(
                        recipe_id=recipe_id,
                        raw_type=block_type,
                        reason=str(exc),
                    )
                )
                continue
            if recipe is None:
                continue
            result.recipes.append(recipe)

    return result


def _iter_recipe_definitions(text: str) -> list[tuple[str, list[str], int]]:
    definitions: list[tuple[str, list[str], int]] = []
    recipe_index = 0

    for block_type, lines in _split_recipe_blocks(text):
        recipe_index += 1
        definitions.append((block_type, lines, recipe_index))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("import="):
            continue
        inline_match = _INLINE_RECIPE.match(line)
        if inline_match is None or "->" not in inline_match.group("body"):
            continue
        block_type = inline_match.group("type")
        if block_type in _MULTILINE_BLOCK_TYPES:
            continue
        body = inline_match.group("body").strip()
        input_part, _, output_part = body.partition("->")
        inline_lines = [
            token
            for token in input_part.split()
            if token and token != "_"
        ]
        inline_lines.append(f"-> {output_part.strip()}")
        recipe_index += 1
        definitions.append((block_type, inline_lines, recipe_index))

    return definitions


def _build_context(recipe_root: Path, version: str) -> _Ae2RecipeContext:
    ore_dict = load_ore_dict(version)
    context = _Ae2RecipeContext(version=version, ore_dict=ore_dict)
    context.ae2_tokens = _build_ae2_token_map(version, ore_dict)
    for recipe_file in recipe_root.rglob("*.recipe"):
        for line in recipe_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            ore_match = _ORE_LINE.match(stripped)
            if ore_match:
                context.ore_to_ae2[ore_match.group("target")] = ore_match.group("source")
                continue
            group_match = _GROUP_LINE.match(stripped)
            if group_match:
                options = [part.strip() for part in group_match.group("options").split()]
                context.groups[group_match.group("alias")] = options
                continue
            alias_match = _ALIAS_LINE.match(stripped)
            if alias_match:
                context.aliases[alias_match.group("from")] = alias_match.group("to")
    return context


def _split_recipe_blocks(text: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_type: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        start_match = _RECIPE_BLOCK_START.match(line)
        if start_match:
            if current_type is not None:
                blocks.append((current_type, current_lines))
            current_type = start_match.group("type")
            current_lines = []
            continue

        if current_type is not None:
            current_lines.append(line)

    if current_type is not None:
        blocks.append((current_type, current_lines))
    return blocks


def _parse_block(
    block_type: str,
    lines: list[str],
    recipe_id: str,
    context: _Ae2RecipeContext,
) -> Recipe | None:
    if not lines:
        return None

    output_line = lines[-1]
    output_match = _OUTPUT_LINE.match(output_line)
    if output_match is None:
        raise ValueError("missing recipe output")

    ingredient_lines = lines[:-1]
    if block_type == "shaped":
        inputs = _parse_shaped_inputs(ingredient_lines, context)
        recipe_type = RecipeType.CRAFTING_SHAPED
        raw_type = CRAFTING_SHAPED
        category_id = CRAFTING_SHAPED
        catalyst_id = "minecraft:crafting_table"
    elif block_type in {"shapeless", "press", "inscribe"}:
        inputs = _parse_shapeless_inputs(ingredient_lines, context)
        if block_type == "shapeless":
            recipe_type = RecipeType.CRAFTING_SHAPELESS
            raw_type = CRAFTING_SHAPELESS
            category_id = CRAFTING_SHAPELESS
            catalyst_id = "minecraft:crafting_table"
        else:
            machine = _AE2_MACHINE_CONFIG[block_type]
            recipe_type, raw_type, catalyst_id = machine
            category_id = raw_type
    elif block_type in _AE2_MACHINE_CONFIG:
        inputs = _parse_shapeless_inputs(ingredient_lines, context)
        recipe_type, raw_type, catalyst_id = _AE2_MACHINE_CONFIG[block_type]
        category_id = raw_type
    else:
        return None

    outputs = _parse_outputs(output_match.group("output"), context)
    if not inputs or not outputs:
        raise ValueError("empty inputs or outputs")

    recipe = Recipe(
        id=recipe_id,
        recipe_type=recipe_type,
        category_id=category_id,
        catalyst_id=catalyst_id,
        inputs=inputs,
        outputs=outputs,
        duration_ticks=None,
        source="ae2:recipe",
        mod_id="appliedenergistics2",
        raw_type=raw_type,
    )
    normalized = normalize_recipe(recipe)
    if normalized is None:
        raise ValueError("empty inputs or outputs after normalization")
    return normalized


def _parse_shaped_inputs(lines: list[str], context: _Ae2RecipeContext) -> list[RecipeIO]:
    inputs: list[RecipeIO] = []
    for line in lines:
        row = line.removesuffix(",").strip()
        if not row:
            continue
        for token in row.split():
            parsed = _resolve_token(token, context)
            if parsed is not None:
                inputs.append(parsed)
    return inputs


def _parse_shapeless_inputs(lines: list[str], context: _Ae2RecipeContext) -> list[RecipeIO]:
    tokens: list[str] = []
    for line in lines:
        row = line.removesuffix(",").strip()
        if row:
            tokens.extend(row.split())
    inputs: list[RecipeIO] = []
    for token in tokens:
        parsed = _resolve_token(token, context)
        if parsed is not None:
            inputs.append(parsed)
    return inputs


def _parse_outputs(raw_output: str, context: _Ae2RecipeContext) -> list[RecipeIO]:
    parts = raw_output.split()
    if not parts:
        return []

    amount = 1.0
    item_token = parts[0]
    if parts[0].isdigit():
        amount = float(parts[0])
        item_token = parts[1] if len(parts) > 1 else ""
    if not item_token:
        return []

    resolved = _resolve_item_token(item_token, context)
    if resolved is None:
        return []
    item_id, metadata = resolved
    return [RecipeIO(item_id=item_id, amount=amount, metadata=metadata)]


def _resolve_token(token: str, context: _Ae2RecipeContext) -> RecipeIO | None:
    if token == "_":
        return None
    resolved = _resolve_item_token(token, context)
    if resolved is None:
        return None
    item_id, metadata = resolved
    return RecipeIO(item_id=item_id, amount=1.0, metadata=metadata)


def _resolve_item_token(token: str, context: _Ae2RecipeContext) -> tuple[str, int | None] | None:
    token = token.strip()
    if not token or token == "_":
        return None

    token, token_metadata = split_trailing_metadata(token)

    if token.startswith(("ae2:ItemPart.", "appliedenergistics2:ItemPart.")):
        part_name = token.rsplit(":", 1)[-1].removeprefix("ItemPart.")
        return f"appliedenergistics2:item.{part_name}", token_metadata

    if token.startswith("oredictionary:"):
        resolved = _resolve_ore_name(token.removeprefix("oredictionary:"), context)
        if resolved is None:
            return None
        item_id, metadata = resolved
        return item_id, token_metadata if token_metadata is not None else metadata

    if token in context.groups:
        for option in context.groups[token]:
            if option.startswith("oredictionary:"):
                resolved = _resolve_ore_name(option.removeprefix("oredictionary:"), context)
                if resolved is not None:
                    item_id, metadata = resolved
                    return item_id, token_metadata if token_metadata is not None else metadata
            else:
                resolved = _resolve_item_token(option, context)
                if resolved is not None:
                    return resolved
        return None

    if token in context.ore_to_ae2:
        return _resolve_item_token(context.ore_to_ae2[token], context)

    if token in context.ae2_tokens:
        item_id, metadata = context.ae2_tokens[token]
        return item_id, token_metadata if token_metadata is not None else metadata

    mod, _, name = token.partition(":")
    mod = context.aliases.get(mod, mod)
    if mod == "mc":
        mod = "minecraft"
    if mod == "ae2":
        mod = "appliedenergistics2"

    if mod == "minecraft":
        return f"minecraft:{name}", token_metadata

    if mod == "appliedenergistics2":
        if name.startswith("ItemMaterial."):
            material_name = name.removeprefix("ItemMaterial.")
            material_token = f"appliedenergistics2:{name}"
            if material_token in context.ae2_tokens:
                item_id, metadata = context.ae2_tokens[material_token]
                return item_id, token_metadata if token_metadata is not None else metadata
            ore_name = next(
                (ore for ore, source in context.ore_to_ae2.items() if source.strip() == token),
                None,
            )
            if ore_name is not None:
                resolved = _resolve_ore_name(ore_name, context)
                if resolved is None:
                    return None
                item_id, metadata = resolved
                return item_id, token_metadata if token_metadata is not None else metadata
            metadata = ae2_item_material_metadata(material_name)
            if metadata is not None:
                return "appliedenergistics2:item.ItemMultiMaterial", (
                    token_metadata if token_metadata is not None else metadata
                )
            return f"appliedenergistics2:item.ItemMaterial.{material_name}", token_metadata
        if name.startswith("Block"):
            return f"appliedenergistics2:tile.{name}", token_metadata
        if name.startswith("ItemPart."):
            part_name = name.removeprefix("ItemPart.")
            return f"appliedenergistics2:item.{part_name}", token_metadata
        if name.startswith("Tool"):
            return f"appliedenergistics2:item.{name}", token_metadata
        if name.startswith("tile.") or name.startswith("item."):
            return f"appliedenergistics2:{name}", token_metadata
        return f"appliedenergistics2:item.{name}", token_metadata

    return f"{mod}:{name}", token_metadata


def _resolve_ore_name(
    ore_name: str,
    context: _Ae2RecipeContext,
) -> tuple[str, int | None] | None:
    for ore_target, ae2_source in context.ore_to_ae2.items():
        if ore_target == ore_name and "ItemPart." in ae2_source:
            resolved = _resolve_item_token(ae2_source.strip(), context)
            if resolved is not None:
                return resolved

    entry = context.ore_dict.get(ore_name)
    if entry is None:
        return None
    metadata = 0 if entry.metadata is None else entry.metadata
    return entry.item_id, metadata
