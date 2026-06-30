import json
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.recipes.loaders.ore_dict_loader import (
    load_ore_dict,
    version_ore_dict_path,
)


def test_load_ore_dict_prefers_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = "1.7.10"
    version_dir = tmp_path / version
    version_dir.mkdir()
    version_file = version_dir / "ore_dict.json"
    version_file.write_text(
        json.dumps({"ingotIron": "minecraft:iron_ingot"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    get_settings.cache_clear()

    entries = load_ore_dict(version)
    assert entries["ingotIron"].item_id == "minecraft:iron_ingot"
    assert version_ore_dict_path(version) == version_file


def test_load_ore_dict_falls_back_to_bundled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = "1.12.2"
    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    get_settings.cache_clear()

    entries = load_ore_dict(version)
    assert entries["gemDiamond"].item_id == "minecraft:diamond"


def test_load_ore_dict_parses_metadata_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = "1.7.10"
    version_dir = tmp_path / version
    version_dir.mkdir()
    (version_dir / "ore_dict.json").write_text(
        json.dumps({"dyeBlue": {"item": "minecraft:dye", "metadata": 4}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    get_settings.cache_clear()

    entries = load_ore_dict(version)
    assert entries["dyeBlue"].item_id == "minecraft:dye"
    assert entries["dyeBlue"].metadata == 4
