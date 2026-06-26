from __future__ import annotations


def recipe_layout_for_version(version: str) -> str:
    if version.startswith("1.7"):
        return "jvm"
    if version.startswith("1.12"):
        return "assets"
    return "data"
