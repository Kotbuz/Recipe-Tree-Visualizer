from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from app.recipes.manager import recipe_manager
from app.recipes.providers.kubejs_data import KubejsDataProvider
from app.recipes.providers.kubejs_paths import (
    is_kubejs_recipe_enabled,
    iter_kubejs_recipe_files,
    recipe_id_from_data_relative,
)
from app.services.kubejs_assets import clear_kubejs_asset_index_cache, resolve_kubejs_item_icon_path
from app.services.profile_service import profile_service
from app.services.version_service import version_service


def test_recipe_id_from_data_relative() -> None:
    assert (
        recipe_id_from_data_relative(
            PurePosixPath("techopolis/recipe/skyblock/cobblestone.json")
        )
        == "techopolis:skyblock/cobblestone"
    )
    assert (
        recipe_id_from_data_relative(PurePosixPath("minecraft/recipe/stick.json"))
        == "minecraft:stick"
    )
    assert recipe_id_from_data_relative(PurePosixPath("techopolis/machine/basic_miner.json")) is None


def test_is_kubejs_recipe_enabled() -> None:
    disabled = {
        "type": "minecraft:crafting_shaped",
        "neoforge:conditions": [{"type": "neoforge:false"}],
    }
    enabled = {
        "type": "minecraft:crafting_shaped",
        "neoforge:conditions": [
            {"type": "bblcore:world_type_condition", "world_type": "minecraft:noise"}
        ],
    }
    assert is_kubejs_recipe_enabled(disabled) is False
    assert is_kubejs_recipe_enabled(enabled) is True


def test_kubejs_data_provider_with_profile_dir(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    version_service.ensure_profiles_layout(version)
    profile = profile_service.create_profile(version, "Kube Test", activate=False)
    kubejs_dir = version_service.kubejs_dir(version, profile.profile_id)

    recipe_dir = kubejs_dir / "data" / "techopolis" / "recipe" / "normal"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "cobblestone.json").write_text(
        json.dumps(
            {
                "type": "minecraft:crafting_shaped",
                "pattern": ["SS", "SS"],
                "key": {"S": {"item": "projectvibrantjourneys:rocks"}},
                "result": {"id": "minecraft:cobblestone", "count": 1},
            }
        ),
        encoding="utf-8",
    )
    disabled_dir = kubejs_dir / "data" / "bucketlib" / "recipe" / "aquaculture"
    disabled_dir.mkdir(parents=True)
    (disabled_dir / "turtle_soup.json").write_text(
        json.dumps(
            {
                "neoforge:conditions": [{"type": "neoforge:false"}],
                "type": "minecraft:crafting_shapeless",
                "ingredients": [{"item": "minecraft:bowl"}],
                "result": {"id": "aquaculture:turtle_soup"},
            }
        ),
        encoding="utf-8",
    )

    recipe_manager._clear_caches()
    provider = KubejsDataProvider()
    result = provider.load(version, profile.profile_id)

    assert len(result.recipes) == 1
    assert result.recipes[0].id == "techopolis:normal/cobblestone"
    assert result.recipes[0].outputs[0].item_id == "minecraft:cobblestone"
    assert any(
        skipped.reason == "disabled by recipe condition"
        for skipped in result.skipped
    )

    merged = recipe_manager.get_version_recipes(
        version,
        profile_id=profile.profile_id,
        include_mods=False,
        include_synthetic=False,
    )
    assert any(recipe.id == "techopolis:normal/cobblestone" for recipe in merged)


def test_kubejs_machine_icon_resolution(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    profile = profile_service.create_profile(version, "Machine Icons", activate=False)
    kubejs_dir = version_service.kubejs_dir(version, profile.profile_id)

    machine_dir = kubejs_dir / "data" / "techopolis" / "machine"
    machine_dir.mkdir(parents=True)
    (machine_dir / "basic_miner.json").write_text(
        json.dumps(
            {
                "appearance": {"custommachinery:block": "techopolis:machine/basic_miner"},
            }
        ),
        encoding="utf-8",
    )

    model_dir = kubejs_dir / "assets" / "techopolis" / "models" / "machine"
    model_dir.mkdir(parents=True)
    (model_dir / "basic_miner.json").write_text(
        json.dumps(
            {
                "textures": {
                    "front": "techopolis:block/basic_miner_front",
                }
            }
        ),
        encoding="utf-8",
    )
    texture_dir = kubejs_dir / "assets" / "techopolis" / "textures" / "block"
    texture_dir.mkdir(parents=True)
    (texture_dir / "basic_miner_front.png").write_bytes(b"png-bytes")

    clear_kubejs_asset_index_cache()
    path = resolve_kubejs_item_icon_path(
        version,
        "basic_miner.png",
        profile_id=profile.profile_id,
    )
    assert path is not None
    assert path.read_bytes() == b"png-bytes"

    resolved = version_service.resolve_item_icon(
        version,
        "basic_miner.png",
        profile_id=profile.profile_id,
    )
    assert resolved is not None
    assert resolved[0] == "file"
    assert resolved[1].read_bytes() == b"png-bytes"


def test_iter_kubejs_recipe_files(tmp_path: Path) -> None:
    kubejs = tmp_path / "kubejs"
    recipe_path = kubejs / "data" / "techopolis" / "recipe" / "skyblock" / "cobblestone.json"
    recipe_path.parent.mkdir(parents=True)
    recipe_path.write_text("{}", encoding="utf-8")

    files = iter_kubejs_recipe_files(kubejs)
    assert len(files) == 1
    assert files[0][0] == "techopolis:skyblock/cobblestone"
