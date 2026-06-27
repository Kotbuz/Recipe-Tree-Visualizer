from __future__ import annotations

import re
from pathlib import Path

_BRACKET_RANGE = re.compile(
    r"^\s*([\[\(])\s*([^,\]\)]*)\s*,\s*([^,\]\)]*)\s*([\]\)])\s*$"
)
_FABRIC_CONSTRAINT = re.compile(
    r"^\s*(>=|<=|>|<|=)?\s*(\d+(?:\.\d+)*)\s*(?:\s+(>=|<=|>|<)\s*(\d+(?:\.\d+)*))?\s*$"
)
_FILENAME_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
_UNRESOLVED_VERSION_MARKERS = ("${", "@file", "@forgeversion")
_UNION_RANGE_SPLIT = re.compile(r"\s*,\s*(?=[\[\(])")


def _is_unresolved_version_label(version: str | None) -> bool:
    if version is None:
        return True
    stripped = version.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    return any(marker in lowered for marker in _UNRESOLVED_VERSION_MARKERS)


def parse_version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for segment in version.strip().split("."):
        digits = "".join(char for char in segment if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    if not parts:
        raise ValueError(f"Invalid version: {version!r}")
    return tuple(parts)


def _compare_versions(left: str, right: str) -> int:
    left_parts = list(parse_version_tuple(left))
    right_parts = list(parse_version_tuple(right))
    max_len = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (max_len - len(left_parts)))
    right_parts.extend([0] * (max_len - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def version_labels_compatible(spec_version: str, game_version: str) -> bool:
    spec_parts = parse_version_tuple(spec_version)
    game_parts = parse_version_tuple(game_version)
    return tuple(game_parts[: len(spec_parts)]) == spec_parts


def version_in_constraint(constraint: str, game_version: str) -> bool:
    normalized = constraint.strip()
    if not normalized:
        return False

    if _UNION_RANGE_SPLIT.search(normalized):
        parts = [part.strip() for part in _UNION_RANGE_SPLIT.split(normalized) if part.strip()]
        if len(parts) > 1:
            return any(version_in_constraint(part, game_version) for part in parts)

    bracket = _BRACKET_RANGE.match(normalized)
    if bracket:
        return _version_in_bracket_range(
            game_version,
            start=bracket.group(2).strip(),
            end=bracket.group(3).strip(),
            start_inclusive=bracket.group(1) == "[",
            end_inclusive=bracket.group(4) == "]",
        )

    fabric = _FABRIC_CONSTRAINT.match(normalized)
    if fabric:
        return _version_in_fabric_constraint(game_version, fabric)

    return version_labels_compatible(normalized, game_version)


def _version_in_bracket_range(
    game_version: str,
    *,
    start: str,
    end: str,
    start_inclusive: bool,
    end_inclusive: bool,
) -> bool:
    if start and end:
        lower_cmp = _compare_versions(game_version, start)
        upper_cmp = _compare_versions(game_version, end)
        lower_ok = lower_cmp > 0 or (start_inclusive and lower_cmp == 0)
        upper_ok = upper_cmp < 0 or (end_inclusive and upper_cmp == 0)
        if lower_ok and upper_ok:
            return True
        return _minecraft_patch_line_compatible(
            game_version,
            start=start,
            end=end,
            start_inclusive=start_inclusive,
            end_inclusive=end_inclusive,
        )

    if start and not end:
        lower_cmp = _compare_versions(game_version, start)
        return lower_cmp > 0 or (start_inclusive and lower_cmp == 0)

    if end and not start:
        upper_cmp = _compare_versions(game_version, end)
        return upper_cmp < 0 or (end_inclusive and upper_cmp == 0)

    return False


def _version_in_fabric_constraint(game_version: str, match: re.Match[str]) -> bool:
    op1, ver1, op2, ver2 = match.groups()
    if op2 and ver2:
        lower_ok = _apply_compare(game_version, ver1, op1 or ">=")
        upper_ok = _apply_compare(game_version, ver2, op2)
        return lower_ok and upper_ok
    return _apply_compare(game_version, ver1, op1 or "=")


def _apply_compare(game_version: str, spec_version: str, operator: str) -> bool:
    cmp = _compare_versions(game_version, spec_version)
    if operator == ">=":
        return cmp >= 0
    if operator == "<=":
        return cmp <= 0
    if operator == ">":
        return cmp > 0
    if operator == "<":
        return cmp < 0
    return cmp == 0


def _minecraft_patch_line_compatible(
    game_version: str,
    *,
    start: str,
    end: str,
    start_inclusive: bool,
    end_inclusive: bool,
) -> bool:
    """NeoForge: [1.21,1.21.1) covers the whole 1.21.x line, including 1.21.1."""
    if end_inclusive or not start or not end:
        return False
    try:
        start_parts = parse_version_tuple(start)
        end_parts = parse_version_tuple(end)
        game_parts = parse_version_tuple(game_version)
    except ValueError:
        return False
    if len(start_parts) < 2 or len(end_parts) < 2:
        return False
    if start_parts[:2] != end_parts[:2] or game_parts[:2] != start_parts[:2]:
        return False
    lower_cmp = _compare_versions(game_version, start)
    return lower_cmp > 0 or (start_inclusive and lower_cmp == 0)


def _looks_like_minecraft_version(candidate: str, *, game_version: str | None = None) -> bool:
    try:
        parts = parse_version_tuple(candidate)
    except ValueError:
        return False
    if parts[0] >= 100:
        return False
    if parts[0] >= 20:
        return True
    if parts[0] != 1:
        return False
    if len(parts) == 2:
        return parts[1] >= 7
    if parts[1] >= 18:
        return True
    if game_version is not None:
        try:
            return _compare_versions(game_version, "1.13") < 0
        except ValueError:
            pass
    return parts[1] >= 7


def infer_minecraft_version_from_filename(
    filename: str,
    *,
    game_version: str | None = None,
) -> str | None:
    stem = Path(filename).stem
    candidates: list[str] = []
    for part in stem.replace("_", "-").split("-"):
        normalized = part[2:] if part.lower().startswith("mc") else part
        if not _FILENAME_VERSION.fullmatch(normalized):
            continue
        if _looks_like_minecraft_version(normalized, game_version=game_version):
            candidates.append(normalized)

    if not candidates:
        return None

    return max(candidates, key=lambda value: (len(parse_version_tuple(value)), value))


def mod_supports_game_version(
    *,
    minecraft_version: str | None,
    minecraft_version_range: str | None,
    jar_path: str,
    game_version: str,
) -> bool:
    if minecraft_version is not None and not _is_unresolved_version_label(minecraft_version):
        try:
            return version_labels_compatible(minecraft_version, game_version)
        except ValueError:
            pass
    if minecraft_version_range is not None and not _is_unresolved_version_label(
        minecraft_version_range
    ):
        try:
            return version_in_constraint(minecraft_version_range, game_version)
        except ValueError:
            pass
    inferred = infer_minecraft_version_from_filename(jar_path, game_version=game_version)
    if inferred is not None:
        return version_labels_compatible(inferred, game_version)
    return True
