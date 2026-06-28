from __future__ import annotations

import re
from dataclasses import dataclass

from app.recipes.models import Recipe, RecipeIO
from app.recipes.providers.kubejs_script_parser import (
    _read_braced_block,
    _read_call_arguments,
    _strip_js_comments,
    normalize_kubejs_item_id,
)
from app.recipes.types import RecipeType

_CM_START = re.compile(
    r"(?:event\.recipes\.custommachinery|recipe)\s*(?:\.\s*)?custom_machine\s*\(",
    re.MULTILINE,
)
_FUNCTION_DEF = re.compile(r"function\s+(\w+)\s*\(([^)]*)\)\s*\{", re.MULTILINE)
_CHAIN_METHOD = re.compile(r"\.(\w+)\s*\(", re.MULTILINE)
_METHOD_CALL = re.compile(
    r"(?:\.|recipe\.)(?:requireItem|requireFluid|produceItem|produceFluid|produceFluidPerTick|produceChemical|id)\s*\(",
    re.MULTILINE,
)
_RECIPE_ANY_LINE = re.compile(r"^\s*recipe\.\w+\s*\(", re.MULTILINE)
_ITEM_OF = re.compile(
    r"Item\.of\s*\(\s*(['\"])(?P<item>.*?)\1\s*,\s*(?P<count>\d+)\s*\)",
    re.DOTALL,
)
_FLUID_PREFIX = re.compile(r"^\d+x\s+", re.IGNORECASE)


@dataclass(frozen=True)
class _ParsedCustomMachine:
    machine_id: str
    duration_ticks: int
    recipe_id: str | None
    item_inputs: tuple[RecipeIO, ...]
    fluid_inputs: tuple[RecipeIO, ...]
    item_outputs: tuple[RecipeIO, ...]
    fluid_outputs: tuple[RecipeIO, ...]
    source_file: str


def parse_custom_machinery_script(content: str, *, source_file: str) -> list[Recipe]:
    stripped = _strip_js_comments(content)
    functions = _parse_function_definitions(stripped)
    expansions = _build_function_expansions(stripped, functions)
    if expansions:
        inline_text = _remove_cm_function_definitions(stripped)
        parse_text = inline_text + "\n\n" + "\n".join(expansions)
    else:
        parse_text = stripped
    parsed_specs: list[_ParsedCustomMachine] = []

    for match in _CM_START.finditer(parse_text):
        spec = _parse_custom_machine_at(parse_text, match.start(), source_file=source_file)
        if spec is not None:
            parsed_specs.append(spec)

    recipes: list[Recipe] = []
    seen_ids: set[str] = set()
    for spec in parsed_specs:
        recipe = _spec_to_recipe(spec)
        if recipe.id in seen_ids:
            suffix = 2
            while f"{recipe.id}#{suffix}" in seen_ids:
                suffix += 1
            recipe = _with_recipe_id(recipe, f"{recipe.id}#{suffix}")
        seen_ids.add(recipe.id)
        recipes.append(recipe)
    return recipes


def parse_custom_machinery_scripts(scripts_dir) -> list[Recipe]:
    from pathlib import Path

    root = Path(scripts_dir)
    if not root.is_dir():
        return []

    recipes: list[Recipe] = []
    for script_path in sorted(root.rglob("*.js")):
        if not script_path.is_file():
            continue
        try:
            content = script_path.read_text(encoding="utf-8")
        except OSError:
            continue
        relative = script_path.relative_to(root).as_posix()
        recipes.extend(parse_custom_machinery_script(content, source_file=relative))
    return recipes


def _remove_cm_function_definitions(content: str) -> str:
    parts: list[str] = []
    last_end = 0
    for match in _FUNCTION_DEF.finditer(content):
        body, body_end = _read_braced_block(content, match.end() - 1)
        if body is None or "custom_machine" not in body:
            continue
        parts.append(content[last_end : match.start()])
        last_end = body_end
    parts.append(content[last_end:])
    return "".join(parts)


def _build_function_expansions(
    content: str,
    functions: dict[str, tuple[list[str], str]],
) -> list[str]:
    if not functions:
        return []

    expansions: list[str] = []
    for name, (params, body) in functions.items():
        call_pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
        for match in call_pattern.finditer(content):
            args, _end = _read_call_arguments(content, match.end())
            if not args or len(args) < len(params):
                continue
            if any("${" in arg for arg in args):
                continue
            expanded_body = body
            for param, arg in zip(params, args):
                expanded_body = re.sub(
                    rf"(?<![.\w]){re.escape(param)}\b",
                    arg,
                    expanded_body,
                )
            expanded_body = _simplify_template_literals(expanded_body)
            expansions.append(expanded_body)
    return expansions


def _expand_function_calls(content: str) -> str:
    functions = _parse_function_definitions(content)
    expansions = _build_function_expansions(content, functions)
    if not expansions:
        return content
    return content + "\n\n" + "\n".join(expansions)


def _simplify_template_literals(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        parts = re.findall(r"\$\{([^}]+)\}", inner)
        if not parts:
            return match.group(0)
        resolved: list[str] = []
        for part in parts:
            value = part.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            resolved.append(value)
        return f'"{"".join(resolved)}"'

    return re.sub(r"`([^`]+)`", repl, text)


def _parse_function_definitions(content: str) -> dict[str, tuple[list[str], str]]:
    functions: dict[str, tuple[list[str], str]] = {}
    for match in _FUNCTION_DEF.finditer(content):
        name = match.group(1)
        params = [part.strip() for part in match.group(2).split(",") if part.strip()]
        body, _end = _read_braced_block(content, match.end() - 1)
        if body is None or "custom_machine" not in body:
            continue
        functions[name] = (params, body[1:-1])
    return functions


def _parse_custom_machine_at(
    content: str,
    start: int,
    *,
    source_file: str,
) -> _ParsedCustomMachine | None:
    open_paren = content.find("(", start)
    if open_paren < 0:
        return None

    args, args_end = _read_call_arguments(content, open_paren + 1)
    if len(args) < 2:
        return None
    if any("${" in arg for arg in args[:2]):
        return None

    machine_id = _unwrap_literal(args[0])
    duration = _parse_duration_ticks(args[1])
    if not machine_id or duration is None:
        return None

    item_inputs: list[RecipeIO] = []
    fluid_inputs: list[RecipeIO] = []
    item_outputs: list[RecipeIO] = []
    fluid_outputs: list[RecipeIO] = []
    recipe_id: str | None = None

    scan_end = _collect_chain_end(content, args_end)
    chain_text = content[args_end:scan_end]
    recipe_lines_end = _collect_recipe_variable_methods(content, scan_end)
    if recipe_lines_end > scan_end:
        chain_text += content[scan_end:recipe_lines_end]

    for method_match in _METHOD_CALL.finditer(chain_text):
        method_token = method_match.group(0)
        method_name = re.sub(r"^(?:\.|recipe\.)", "", method_token).split("(")[0].strip()
        arg_text = _extract_method_argument(chain_text, method_match.end() - 1)
        if arg_text is None:
            continue
        if method_name == "id":
            recipe_id = _unwrap_literal(arg_text.split(",")[0].strip())
            continue
        if method_name == "requireItem":
            io = _parse_item_material(arg_text)
            if io is not None:
                item_inputs.append(io)
        elif method_name == "requireFluid":
            io = _parse_fluid_material(arg_text)
            if io is not None:
                fluid_inputs.append(io)
        elif method_name == "produceItem":
            io = _parse_item_output(arg_text)
            if io is not None:
                item_outputs.append(io)
        elif method_name in {"produceFluid", "produceFluidPerTick", "produceChemical"}:
            io = _parse_fluid_material(arg_text)
            if io is not None:
                fluid_outputs.append(io)

    if not item_outputs and not fluid_outputs:
        return None

    inputs = [*item_inputs, *fluid_inputs]
    if not inputs and not item_outputs and not fluid_outputs:
        return None

    return _ParsedCustomMachine(
        machine_id=machine_id,
        duration_ticks=duration,
        recipe_id=recipe_id,
        item_inputs=tuple(item_inputs),
        fluid_inputs=tuple(fluid_inputs),
        item_outputs=tuple(item_outputs),
        fluid_outputs=tuple(fluid_outputs),
        source_file=source_file,
    )


def _collect_recipe_variable_methods(content: str, start: int) -> int:
    end = start
    while end < len(content):
        line_match = _RECIPE_ANY_LINE.match(content, end)
        if line_match:
            call_end = _find_call_end(content, content.find("(", line_match.start()))
            end = call_end if call_end > end else line_match.end()
            continue
        if content[end : end + 1] in {" ", "\t", "\r", "\n"}:
            end += 1
            continue
        break
    return end


def _collect_chain_end(content: str, start: int) -> int:
    end = start
    while end < len(content):
        stripped = content[end:].lstrip()
        if stripped and _CM_START.match(content, end + (len(content[end:]) - len(stripped))):
            break

        method = _METHOD_CALL.search(content, end)
        if method is not None and method.start() <= end + 80:
            arg_end = _find_call_end(content, method.end() - 1)
            end = arg_end if arg_end > end else method.end()
            continue

        chain_method = _CHAIN_METHOD.search(content, end)
        if chain_method is not None and chain_method.start() <= end + 80:
            arg_end = _find_call_end(content, chain_method.end() - 1)
            end = arg_end if arg_end > end else chain_method.end()
            continue

        line_match = _RECIPE_ANY_LINE.match(content, end)
        if line_match:
            call_end = _find_call_end(content, content.find("(", line_match.start()))
            end = call_end if call_end > end else line_match.end()
            continue

        if content[end : end + 1] in {";", "\n"}:
            next_pos = end + 1
            if (
                _METHOD_CALL.search(content, next_pos)
                or _CHAIN_METHOD.search(content, next_pos)
                or _RECIPE_ANY_LINE.match(content, next_pos)
            ):
                end = next_pos
                continue
            break
        if content[end : end + 1] == "}":
            break
        if content[end : end + 1] not in {" ", "\t", "\r", "\n"}:
            break
        end += 1
    return end


def _find_call_end(content: str, open_paren_index: int) -> int:
    if open_paren_index >= len(content) or content[open_paren_index] != "(":
        return open_paren_index
    depth = 0
    in_string: str | None = None
    escape = False
    index = open_paren_index
    while index < len(content):
        char = content[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            index += 1
            continue
        if char in {"'", '"'}:
            in_string = char
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return open_paren_index


def _extract_method_argument(text: str, open_paren_index: int) -> str | None:
    if open_paren_index >= len(text) or text[open_paren_index] != "(":
        return None
    end = _find_call_end(text, open_paren_index)
    return text[open_paren_index + 1 : end - 1].strip()


def _spec_to_recipe(spec: _ParsedCustomMachine) -> Recipe:
    outputs = [*spec.item_outputs, *spec.fluid_outputs]
    primary_output = outputs[0]
    recipe_id = spec.recipe_id or _generated_recipe_id(spec.machine_id, primary_output.item_id)
    mod_id = spec.machine_id.split(":", 1)[0]
    return Recipe(
        id=recipe_id,
        recipe_type=RecipeType.CRAFTING_SHAPELESS,
        category_id=f"custommachinery:{spec.machine_id}",
        catalyst_id=spec.machine_id,
        inputs=[*spec.item_inputs, *spec.fluid_inputs],
        outputs=outputs,
        duration_ticks=spec.duration_ticks,
        source=f"kubejs_scripts:{spec.source_file}",
        mod_id=mod_id,
        raw_type="custommachinery:custom_machine",
    )


def _with_recipe_id(recipe: Recipe, recipe_id: str) -> Recipe:
    return Recipe(
        id=recipe_id,
        recipe_type=recipe.recipe_type,
        category_id=recipe.category_id,
        catalyst_id=recipe.catalyst_id,
        inputs=recipe.inputs,
        outputs=recipe.outputs,
        duration_ticks=recipe.duration_ticks,
        source=recipe.source,
        mod_id=recipe.mod_id,
        raw_type=recipe.raw_type,
    )


def _generated_recipe_id(machine_id: str, output_item_id: str) -> str:
    suffix = output_item_id.removeprefix("fluid:").split(":", 1)[-1]
    suffix = suffix.replace("/", "_")
    return f"{machine_id}/{suffix}"


def _unwrap_literal(raw: str) -> str | None:
    value = raw.strip().strip("'\"`")
    if not value or value == "null" or "${" in value:
        return None
    return normalize_kubejs_item_id(value)


def _parse_duration_ticks(raw: str) -> int | None:
    value = raw.strip()
    if not value or value == "null" or "${" in value:
        return None
    if value.isdigit():
        return int(value)
    if re.fullmatch(r"[\d\s*+\-]+", value):
        try:
            return int(eval(value, {"__builtins__": {}}, {}))  # noqa: S307
        except (SyntaxError, TypeError, ValueError):
            return None
    return None


def _parse_item_material(raw: str) -> RecipeIO | None:
    first_arg = raw.split(",")[0].strip()
    item_of = _ITEM_OF.search(first_arg) or _ITEM_OF.search(raw)
    if item_of:
        item_id = normalize_kubejs_item_id(item_of.group("item"))
        return RecipeIO(item_id=item_id, amount=float(item_of.group("count")))
    literal = _unwrap_literal(first_arg)
    if literal is None:
        return None
    amount = 1.0
    text = first_arg.strip().strip("'\"`")
    count_match = re.match(r"^(\d+)x\s+(.+)$", text, flags=re.IGNORECASE)
    if count_match:
        amount = float(count_match.group(1))
        literal = normalize_kubejs_item_id(count_match.group(2))
    return RecipeIO(item_id=literal, amount=amount)


def _parse_item_output(raw: str) -> RecipeIO | None:
    item_of = _ITEM_OF.search(raw)
    if item_of:
        item_id = normalize_kubejs_item_id(item_of.group("item"))
        return RecipeIO(item_id=item_id, amount=float(item_of.group("count")))
    return _parse_item_material(raw.split(",")[0])


def _parse_fluid_material(raw: str) -> RecipeIO | None:
    first_arg = raw.split(",")[0].strip()
    literal = _unwrap_literal(first_arg)
    if literal is None:
        return None
    amount = 1.0
    text = first_arg.strip().strip("'\"`")
    if _FLUID_PREFIX.match(text):
        amount_str, rest = text.split("x", 1)
        amount = float(amount_str.strip())
        literal = normalize_kubejs_item_id(rest.strip())
    fluid_id = literal if literal.startswith("fluid:") else f"fluid:{literal}"
    return RecipeIO(item_id=fluid_id, amount=amount)
