import json
from pathlib import Path

import pytest

from app.recipes.manager import RecipeLookup, _build_version_recipe_bundle
from app.recipes.models import Recipe, RecipeIO
from app.recipes.registry import IngredientRegistry
from app.recipes.types import RecipeType
from app.services.recipe_snapshot_service import (
    commit_snapshot,
    load_snapshot_recipes,
    read_snapshot_status,
)


def test_commit_and_load_snapshot(tmp_path, monkeypatch) -> None:
    from app.services import version_service as version_service_module

    version = "1.21.1"
    profile_id = "technopolis"
    profile_dir = tmp_path / version / "profiles" / profile_id
    profile_dir.mkdir(parents=True)

    monkeypatch.setattr(
        version_service_module.version_service,
        "profile_dir",
        lambda v, pid: tmp_path / v / "profiles" / pid,
    )

    snapshot_payload = {
        "format_version": 1,
        "minecraft_version": version,
        "recipes": {
            "minecraft:stick": {
                "type": "minecraft:crafting_shaped",
                "pattern": ["#", "#"],
                "key": {"#": {"item": "minecraft:planks"}},
                "result": {"item": "minecraft:stick", "count": 4},
            }
        },
    }
    meta = {
        "format_version": 1,
        "minecraft_version": version,
        "loader": "neoforge",
        "loader_version": "21.1.89",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "recipe_count": 1,
    }
    commit_snapshot(version, profile_id, snapshot_payload=snapshot_payload, meta=meta)

    status = read_snapshot_status(version, profile_id)
    assert status.has_snapshot is True
    assert status.recipe_count == 1

    recipes = load_snapshot_recipes(version, profile_id)
    assert recipes is not None
    assert len(recipes) == 1
    assert recipes[0].id == "minecraft:stick"


def test_manager_prefers_snapshot_over_jar(tmp_path, monkeypatch) -> None:
    from app.recipes.manager import recipe_manager
    from app.services import version_service as version_service_module

    version = "1.21.1"
    profile_id = "technopolis"
    profile_dir = tmp_path / version / "profiles" / profile_id
    profile_dir.mkdir(parents=True)

    monkeypatch.setattr(
        version_service_module.version_service,
        "profile_dir",
        lambda v, pid: tmp_path / v / "profiles" / pid,
    )

    snapshot_payload = {
        "format_version": 1,
        "minecraft_version": version,
        "recipes": {
            "test:snapshot_only": {
                "type": "minecraft:crafting_shapeless",
                "ingredients": [{"item": "minecraft:stick"}],
                "result": {"item": "minecraft:torch", "count": 4},
            }
        },
    }
    meta = {
        "format_version": 1,
        "minecraft_version": version,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "recipe_count": 1,
    }
    commit_snapshot(version, profile_id, snapshot_payload=snapshot_payload, meta=meta)
    recipe_manager.clear_version_cache(version, profile_id=profile_id)

    bundle = recipe_manager.get_recipe_bundle(version, profile_id=profile_id, include_mods=False)
    assert any(recipe.id == "test:snapshot_only" for recipe in bundle.recipes)
