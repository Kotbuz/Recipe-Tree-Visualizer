from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.kubejs_import import (
    copy_kubejs_from_directory,
    should_import_kubejs_relative_path,
)
from app.services.version_service import version_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("server_scripts/recipes.js", "server_scripts"),
        ("server_scripts/sub/foo.js", "server_scripts"),
        ("data/techopolis/recipe/skyblock/cobblestone.json", "data"),
        ("data/techopolis/machine/basic_miner.json", "data"),
        ("data/bucketlib/recipe/aquaculture/turtle_soup.json", "data"),
        ("assets/techopolis/models/machine/basic_miner.json", "assets"),
        ("assets/techopolis/textures/block/basic_miner_front.png", "assets"),
        ("assets/techopolis/textures/gui/fluid_injector_background.png", "assets"),
        ("data/techopolis/catalogs/techopolis.json", None),
        ("data/techopolis/loot_modifiers/add_pumpkin.json", None),
        ("assets/techopolis/guides/techopolis/guide/pump.md", None),
        ("client_scripts/main.js", None),
        ("startup_scripts/init.js", None),
    ],
)
def test_should_import_kubejs_relative_path(relative: str, expected: str | None) -> None:
    assert should_import_kubejs_relative_path(PurePosixPath(relative)) == expected


def test_copy_kubejs_from_directory_filters_non_recipe_data(tmp_path: Path) -> None:
    kubejs = tmp_path / "kubejs"
    (kubejs / "server_scripts").mkdir(parents=True)
    (kubejs / "server_scripts" / "recipes.js").write_text("// js", encoding="utf-8")
    (kubejs / "data" / "techopolis" / "recipe" / "normal").mkdir(parents=True)
    (kubejs / "data" / "techopolis" / "recipe" / "normal" / "cobblestone.json").write_text(
        "{}", encoding="utf-8"
    )
    (kubejs / "data" / "techopolis" / "machine").mkdir(parents=True)
    (kubejs / "data" / "techopolis" / "machine" / "basic_miner.json").write_text(
        "{}", encoding="utf-8"
    )
    (kubejs / "data" / "techopolis" / "catalogs").mkdir(parents=True)
    (kubejs / "data" / "techopolis" / "catalogs" / "techopolis.json").write_text(
        "{}", encoding="utf-8"
    )
    (kubejs / "assets" / "techopolis" / "models" / "machine").mkdir(parents=True)
    (kubejs / "assets" / "techopolis" / "models" / "machine" / "basic_miner.json").write_text(
        "{}", encoding="utf-8"
    )
    (kubejs / "assets" / "techopolis" / "textures" / "block").mkdir(parents=True)
    (kubejs / "assets" / "techopolis" / "textures" / "block" / "basic_miner_front.png").write_bytes(
        b"png"
    )
    (kubejs / "assets" / "techopolis" / "guides").mkdir(parents=True)
    (kubejs / "assets" / "techopolis" / "guides" / "readme.md").write_text("# x", encoding="utf-8")

    destination = tmp_path / "profile" / "kubejs"
    stats = copy_kubejs_from_directory(kubejs, destination)

    assert stats.server_script_files == 1
    assert stats.data_files == 2
    assert stats.asset_files == 2
    assert (destination / "server_scripts" / "recipes.js").is_file()
    assert (destination / "data" / "techopolis" / "recipe" / "normal" / "cobblestone.json").is_file()
    assert (destination / "data" / "techopolis" / "machine" / "basic_miner.json").is_file()
    assert not (destination / "data" / "techopolis" / "catalogs" / "techopolis.json").exists()
    assert not (destination / "assets" / "techopolis" / "guides" / "readme.md").exists()


def test_import_from_instance_path_copies_kubejs_from_minecraft_subfolder(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    instance = tmp_path / "Techopolis"
    (instance / "minecraft" / "mods").mkdir(parents=True)
    (instance / "minecraft" / "mods" / "techopolis.jar").write_bytes(b"jar")
    kubejs = instance / "minecraft" / "kubejs"
    (kubejs / "server_scripts").mkdir(parents=True)
    (kubejs / "server_scripts" / "recipes.js").write_text("// js", encoding="utf-8")
    (kubejs / "data" / "techopolis" / "recipe" / "skyblock").mkdir(parents=True)
    (kubejs / "data" / "techopolis" / "recipe" / "skyblock" / "cobblestone.json").write_text(
        "{}", encoding="utf-8"
    )
    (kubejs / "data" / "techopolis" / "loot_modifiers").mkdir(parents=True)
    (kubejs / "data" / "techopolis" / "loot_modifiers" / "skip.json").write_text("{}", encoding="utf-8")

    response = client.post(
        f"/versions/{version}/profiles/import-path",
        json={"path": str(instance), "name": "Techopolis KubeJS"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kubejs_server_scripts_imported"] == 1
    assert payload["kubejs_data_files_imported"] == 1
    assert payload["kubejs_asset_files_imported"] == 0

    profile_id = payload["profile"]["profile_id"]
    kubejs_dir = version_service.kubejs_dir(version, profile_id)
    assert (kubejs_dir / "server_scripts" / "recipes.js").is_file()
    assert (
        kubejs_dir / "data" / "techopolis" / "recipe" / "skyblock" / "cobblestone.json"
    ).is_file()
    assert not (kubejs_dir / "data" / "techopolis" / "loot_modifiers" / "skip.json").exists()


def test_import_modpack_zip_copies_kubejs(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("overrides/mods/mod.jar", b"jar")
        zf.writestr("overrides/kubejs/server_scripts/main.js", b"// js")
        zf.writestr(
            "overrides/kubejs/data/techopolis/machine/basic_miner.json",
            b"{}",
        )
        zf.writestr(
            "overrides/kubejs/assets/techopolis/textures/gui/bg.png",
            b"png",
        )
        zf.writestr("overrides/kubejs/assets/techopolis/tips/sky_grid.json", b"{}")

    with archive.open("rb") as handle:
        response = client.post(
            f"/versions/{version}/profiles/import-modpack",
            files={"file": ("pack.zip", handle, "application/zip")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kubejs_server_scripts_imported"] == 1
    assert payload["kubejs_data_files_imported"] == 1
    assert payload["kubejs_asset_files_imported"] == 1

    kubejs_dir = version_service.kubejs_dir(version, payload["profile"]["profile_id"])
    assert (kubejs_dir / "server_scripts" / "main.js").is_file()
    assert (kubejs_dir / "data" / "techopolis" / "machine" / "basic_miner.json").is_file()
    assert (kubejs_dir / "assets" / "techopolis" / "textures" / "gui" / "bg.png").is_file()
    assert not (kubejs_dir / "assets" / "techopolis" / "tips" / "sky_grid.json").exists()
