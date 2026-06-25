from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

ADVANCEMENT_SEGMENT = "/advancement/"
DATA_RECIPE_PATH = re.compile(r"^data/([^/]+)/recipes?/(.+\.json)$")
ASSETS_RECIPE_PATH = re.compile(r"^assets/([^/]+)/recipes/(.+\.json)$")

_SKIP_RECIPE_NAMES = frozenset({"_constants", "_factories", "_defaults"})


@dataclass(frozen=True)
class DiscoveredRecipeFile:
    recipe_id: str
    namespace: str
    filename: str


def recipe_layout_for_version(version: str) -> str:
    if version.startswith("1.7"):
        return "jvm"
    if version.startswith("1.12"):
        return "assets"
    return "data"


def jar_recipe_patterns_for_version(version: str) -> tuple[re.Pattern[str], ...]:
    layout = recipe_layout_for_version(version)
    if layout == "assets":
        return (ASSETS_RECIPE_PATH,)
    return (DATA_RECIPE_PATH,)


def mod_jar_recipe_patterns() -> tuple[re.Pattern[str], ...]:
    return (DATA_RECIPE_PATH, ASSETS_RECIPE_PATH)


def is_recipe_entry(path: str) -> bool:
    if ADVANCEMENT_SEGMENT in path:
        return False
    if not path.endswith(".json"):
        return False
    stem = PurePosixPath(path).stem
    if stem.startswith("_") or stem in _SKIP_RECIPE_NAMES:
        return False
    if "/aerecipes/" in path:
        return False
    return bool(DATA_RECIPE_PATH.match(path) or ASSETS_RECIPE_PATH.match(path))


def discover_recipe_file(path: str) -> DiscoveredRecipeFile | None:
    if not is_recipe_entry(path):
        return None

    match = DATA_RECIPE_PATH.match(path) or ASSETS_RECIPE_PATH.match(path)
    if match is None:
        return None

    namespace, relative_path = match.groups()
    recipe_name = PurePosixPath(relative_path).stem
    return DiscoveredRecipeFile(
        recipe_id=f"{namespace}:{recipe_name}",
        namespace=namespace,
        filename=path,
    )
