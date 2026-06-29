from __future__ import annotations

import json
import re
from pathlib import Path

from app.recipes.providers.kubejs_script_models import KubejsRecipeRemove, KubejsScriptParseResult

_REMOVE_CALL = re.compile(r"event\.remove\s*\(\s*\{", re.MULTILINE)
_SHAPED_CALL = re.compile(r"event\.shaped\s*\(", re.MULTILINE)
_SHAPELESS_CALL = re.compile(r"event\.shapeless\s*\(", re.MULTILINE)
_CUSTOM_CALL = re.compile(r"event\.custom\s*\(\s*\{", re.MULTILINE)
_ID_CHAIN = re.compile(r"\.id\s*\(\s*(['\"`])(?P<id>.*?)\1\s*\)", re.DOTALL)

_REMOVE_FIELD = re.compile(
    r"(?P<key>id|output|mod|type)\s*:\s*(?P<quote>['\"`])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def parse_kubejs_server_script(content: str, *, source_file: str) -> KubejsScriptParseResult:
    result = KubejsScriptParseResult()
    stripped = _strip_js_comments(content)

    for match in _REMOVE_CALL.finditer(stripped):
        object_text, _end = _read_braced_block(stripped, match.end() - 1)
        if object_text is None:
            continue
        remove = _parse_remove_object(object_text, source_file=source_file)
        if remove is not None:
            result.removes.append(remove)
        elif "${" in object_text:
            result.dynamic_expressions += 1

    for pattern, builder in (
        (_SHAPED_CALL, _build_shaped_recipe),
        (_SHAPELESS_CALL, _build_shapeless_recipe),
    ):
        for match in pattern.finditer(stripped):
            args, end = _read_call_arguments(stripped, match.end())
            if not args:
                if "${" in stripped[match.start() : match.start() + 400]:
                    result.dynamic_expressions += 1
                continue
            recipe_id = _read_chained_id(stripped, end)
            payload = builder(args)
            if payload is None:
                if any("${" in arg for arg in args):
                    result.dynamic_expressions += 1
                continue
            payload["__recipe_id"] = recipe_id
            payload["__source_file"] = source_file
            result.recipe_payloads.append(payload)

    for match in _CUSTOM_CALL.finditer(stripped):
        object_text, end = _read_braced_block(stripped, match.end() - 1)
        if object_text is None:
            continue
        if "${" in object_text:
            result.dynamic_expressions += 1
            continue
        recipe_id = _read_chained_id(stripped, end)
        try:
            payload = json.loads(_js_object_to_json(object_text))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        payload["__recipe_id"] = recipe_id
        payload["__source_file"] = source_file
        result.recipe_payloads.append(payload)

    return result


def parse_kubejs_server_scripts(scripts_dir: Path) -> KubejsScriptParseResult:
    combined = KubejsScriptParseResult()
    if not scripts_dir.is_dir():
        return combined

    for script_path in sorted(scripts_dir.rglob("*.js")):
        if not script_path.is_file():
            continue
        try:
            content = script_path.read_text(encoding="utf-8")
        except OSError:
            continue
        relative = script_path.relative_to(scripts_dir).as_posix()
        parsed = parse_kubejs_server_script(content, source_file=relative)
        combined.removes.extend(parsed.removes)
        combined.recipe_payloads.extend(parsed.recipe_payloads)
        combined.dynamic_expressions += parsed.dynamic_expressions
    return combined


def apply_kubejs_removes(recipes: dict[str, object], removes: list[KubejsRecipeRemove]) -> set[str]:
    removed_ids: set[str] = set()
    if not removes:
        return removed_ids

    for remove in removes:
        if remove.recipe_id:
            for key in list(recipes.keys()):
                if _recipe_id_matches_remove(key, remove.recipe_id):
                    removed_ids.add(key)
                    del recipes[key]

        if remove.output_item_id:
            target = normalize_kubejs_item_id(remove.output_item_id)
            for key, recipe in list(recipes.items()):
                outputs = getattr(recipe, "outputs", None)
                if not outputs:
                    continue
                if any(normalize_kubejs_item_id(part.item_id) == target for part in outputs):
                    removed_ids.add(key)
                    del recipes[key]

        if remove.mod_id:
            prefix = f"{remove.mod_id}:"
            for key in list(recipes.keys()):
                recipe = recipes[key]
                mod_id = getattr(recipe, "mod_id", None)
                if key.startswith(prefix) or mod_id == remove.mod_id:
                    removed_ids.add(key)
                    del recipes[key]

        if remove.recipe_type:
            normalized_type = remove.recipe_type.removeprefix("minecraft:")
            for key, recipe in list(recipes.items()):
                raw_type = getattr(recipe, "raw_type", "") or ""
                recipe_type = getattr(recipe, "recipe_type", None)
                type_value = recipe_type.value if recipe_type is not None else ""
                if (
                    raw_type == remove.recipe_type
                    or raw_type == normalized_type
                    or type_value == normalized_type
                    or type_value == remove.recipe_type
                ):
                    removed_ids.add(key)
                    del recipes[key]

    return removed_ids


def normalize_kubejs_item_id(raw: str) -> str:
    value = raw.strip().strip("'\"`")
    if value.startswith("#"):
        tag = value.removeprefix("#")
        return f"tag:{tag}" if not tag.startswith("tag:") else tag

    count_match = re.match(r"^(\d+)x\s+(.+)$", value, flags=re.IGNORECASE)
    if count_match:
        value = count_match.group(2).strip()

    if ":" not in value:
        return f"minecraft:{value}"
    return value


def parse_kubejs_output(raw: str) -> tuple[str, int]:
    value = raw.strip().strip("'\"`")
    count_match = re.match(r"^(\d+)x\s+(.+)$", value, flags=re.IGNORECASE)
    if count_match:
        return normalize_kubejs_item_id(count_match.group(2)), int(count_match.group(1))
    return normalize_kubejs_item_id(value), 1


def parse_kubejs_ingredient(raw: str) -> dict[str, object] | str:
    value = raw.strip()
    if not value:
        raise ValueError("empty ingredient")

    value = _unwrap_js_string(value) if value[0] in {"'", '"', "`"} else value.strip().rstrip(",")

    if value.startswith("#"):
        tag = value.removeprefix("#")
        return {"tag": tag}
    if value.startswith("tag:"):
        return {"tag": value.removeprefix("tag:")}

    item_id = normalize_kubejs_item_id(value)
    return {"item": item_id}


def _parse_remove_object(object_text: str, *, source_file: str) -> KubejsRecipeRemove | None:
    if "${" in object_text:
        return None

    fields: dict[str, str] = {}
    for match in _REMOVE_FIELD.finditer(object_text):
        fields[match.group("key")] = match.group("value")

    if not fields:
        return None

    return KubejsRecipeRemove(
        recipe_id=fields.get("id"),
        output_item_id=fields.get("output"),
        mod_id=fields.get("mod"),
        recipe_type=fields.get("type"),
        source_file=source_file,
    )


def _build_shaped_recipe(args: list[str]) -> dict[str, object] | None:
    if len(args) < 3:
        return None
    if any("${" in arg for arg in args[:3]):
        return None

    output_id, output_count = parse_kubejs_output(args[0])
    pattern = _parse_js_string_array(args[1])
    key = _parse_js_object(args[2])
    if pattern is None or key is None:
        return None

    shaped_key: dict[str, object] = {}
    for symbol, ingredient_raw in key.items():
        shaped_key[symbol] = parse_kubejs_ingredient(str(ingredient_raw))

    return {
        "type": "minecraft:crafting_shaped",
        "pattern": pattern,
        "key": shaped_key,
        "result": {"id": output_id, "count": output_count},
    }


def _build_shapeless_recipe(args: list[str]) -> dict[str, object] | None:
    if len(args) < 2:
        return None
    if any("${" in arg for arg in args[:2]):
        return None

    output_id, output_count = parse_kubejs_output(args[0])
    ingredients = _parse_js_string_array(args[1])
    if ingredients is None:
        return None

    return {
        "type": "minecraft:crafting_shapeless",
        "ingredients": [parse_kubejs_ingredient(item) for item in ingredients],
        "result": {"id": output_id, "count": output_count},
    }


def _recipe_id_matches_remove(recipe_id: str, remove_id: str) -> bool:
    if recipe_id == remove_id:
        return True
    if recipe_id.endswith(f"/{remove_id}") or remove_id.endswith(f"/{recipe_id}"):
        return True
    recipe_tail = recipe_id.split(":", 1)[-1]
    remove_tail = remove_id.split(":", 1)[-1]
    return recipe_tail == remove_tail


def _read_chained_id(text: str, start: int) -> str | None:
    slice_ = text[start : start + 200]
    match = _ID_CHAIN.search(slice_)
    if match is None:
        return None
    return match.group("id")


def _read_call_arguments(text: str, start: int) -> tuple[list[str], int]:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text):
        return [], start

    if text[index] == "(":
        index += 1

    args: list[str] = []
    current: list[str] = []
    depth_paren = 1
    depth_square = 0
    depth_brace = 0
    in_string: str | None = None
    escape = False
    template_depth = 0

    while index < len(text):
        char = text[index]

        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string and in_string != "`":
                in_string = None
            elif char == "`" and in_string == "`":
                if template_depth == 0:
                    in_string = None
                else:
                    template_depth -= 1
            elif (
                char == "$"
                and in_string == "`"
                and index + 1 < len(text)
                and text[index + 1] == "{"
            ):
                template_depth += 1
            index += 1
            continue

        if char in {"'", '"', "`"}:
            in_string = char
            current.append(char)
            index += 1
            continue

        if char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren -= 1
            if depth_paren == 0:
                arg = "".join(current).strip()
                if arg:
                    args.append(arg)
                return args, index + 1
        elif char == "[":
            depth_square += 1
        elif char == "]":
            depth_square -= 1
        elif char == "{":
            depth_brace += 1
        elif char == "}":
            depth_brace -= 1
        elif char == "," and depth_paren == 1 and depth_square == 0 and depth_brace == 0:
            arg = "".join(current).strip()
            if arg:
                args.append(arg)
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    return [], start


def _read_braced_block(text: str, open_index: int) -> tuple[str | None, int]:
    if open_index >= len(text) or text[open_index] != "{":
        return None, open_index

    depth = 0
    in_string: str | None = None
    escape = False
    start = open_index
    index = open_index

    while index < len(text):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            in_string = char
            index += 1
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
        index += 1

    return None, open_index


def _parse_js_string_array(raw: str) -> list[str] | None:
    raw = raw.strip()
    if not raw.startswith("[") or not raw.endswith("]"):
        return None
    inner = raw[1:-1].strip()
    if not inner:
        return []

    items: list[str] = []
    current: list[str] = []
    in_string: str | None = None
    escape = False

    for char in inner:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue

        if char in {"'", '"'}:
            in_string = char
            current.append(char)
            continue

        if char == ",":
            item = "".join(current).strip()
            if item:
                items.append(_unwrap_js_string(item))
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        items.append(_unwrap_js_string(tail))
    return items


def _parse_js_object(raw: str) -> dict[str, str] | None:
    raw = raw.strip()
    if not raw.startswith("{") or not raw.endswith("}"):
        return None

    inner = raw[1:-1]
    entries: dict[str, str] = {}
    key: str | None = None
    current: list[str] = []
    in_string: str | None = None
    escape = False
    reading_key = True

    for char in inner:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue

        if char in {"'", '"'}:
            in_string = char
            current.append(char)
            continue

        if reading_key:
            if char == ":":
                key = "".join(current).strip().strip("'\"")
                current = []
                reading_key = False
            else:
                current.append(char)
            continue

        if char == ",":
            value = "".join(current).strip()
            if key is not None and value:
                entries[key] = value
            key = None
            current = []
            reading_key = True
            continue

        current.append(char)

    if key is not None:
        value = "".join(current).strip()
        if value:
            entries[key] = value

    return entries


def _unwrap_js_string(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"', "`"}:
        return raw[1:-1]
    return raw


def _js_object_to_json(object_text: str) -> str:
    converted = object_text
    converted = re.sub(
        r"([,{]\s*)([A-Za-z_][\w]*)\s*:",
        r'\1"\2":',
        converted,
    )
    converted = converted.replace("'", '"')
    converted = re.sub(r",(\s*[}\]])", r"\1", converted)
    return converted


def _strip_js_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    length = len(text)
    in_string: str | None = None
    escape = False

    while index < length:
        char = text[index]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            in_string = char
            result.append(char)
            index += 1
            continue

        if char == "/" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "/":
                index += 2
                while index < length and text[index] not in "\r\n":
                    index += 1
                result.append(" ")
                continue
            if nxt == "*":
                index += 2
                while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                    index += 1
                index += 2
                result.append(" ")
                continue

        result.append(char)
        index += 1

    return "".join(result)
