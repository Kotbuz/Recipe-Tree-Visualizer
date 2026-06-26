from __future__ import annotations

import zipfile
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.profile_service import profile_service
from app.services.version_service import version_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_legacy_mods_migrated_to_default_profile(isolated_minecraft_versions: Path) -> None:
    import shutil

    version = "1.7.10"
    version_dir = isolated_minecraft_versions / version
    profiles_dir = version_dir / "profiles"
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir)

    legacy_mods = version_dir / "mods"
    legacy_mods.mkdir(parents=True, exist_ok=True)
    (legacy_mods / "legacy-mod.jar").write_bytes(b"fake")

    version_service.ensure_profiles_layout(version)

    profile_mods = version_service.mods_dir(version, "default")
    assert profile_mods.is_dir()
    assert (profile_mods / "legacy-mod.jar").is_file()
    assert not legacy_mods.exists()


def test_import_modpack_zip_curseforge_dual_mod_paths(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    """CurseForge: часть jar в overrides/mods/, часть в overrides/mods/{version}/."""
    version = "1.7.10"
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("overrides/mods/1.7.10/CodeChickenLib.jar", b"jar")
        zf.writestr("overrides/mods/GalacticraftCore.jar", b"jar")
        zf.writestr("overrides/mods/ic2/nested-lib.jar", b"jar")
        zf.writestr("overrides/config/test.cfg", b"cfg=1")

    with archive.open("rb") as handle:
        response = client.post(
            f"/versions/{version}/profiles/import-modpack",
            files={"file": ("pack.zip", handle, "application/zip")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jars_imported"] == 3
    profile_id = payload["profile"]["profile_id"]
    mods_dir = version_service.mods_dir(version, profile_id)
    assert (mods_dir / "CodeChickenLib.jar").is_file()
    assert (mods_dir / "GalacticraftCore.jar").is_file()
    assert (mods_dir / "nested-lib.jar").is_file()


def test_import_modpack_zip_curseforge_layout(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("overrides/mods/1.7.10/AE2.jar", b"jar")
        zf.writestr("overrides/config/test.cfg", b"cfg=1")

    with archive.open("rb") as handle:
        response = client.post(
            f"/versions/{version}/profiles/import-modpack",
            files={"file": ("pack.zip", handle, "application/zip")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jars_imported"] == 1
    assert payload["profile"]["mod_count"] == 1

    mods_dir = version_service.mods_dir(version, payload["profile"]["profile_id"])
    assert (mods_dir / "AE2.jar").is_file()
    config_dir = version_service.config_dir(version, payload["profile"]["profile_id"])
    assert (config_dir / "test.cfg").is_file()


def test_delete_profile_removes_files(client: TestClient, isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    version_service.ensure_profiles_layout(version)
    profile = profile_service.create_profile(version, "Temp Pack", activate=False)
    mods_dir = version_service.mods_dir(version, profile.profile_id)
    (mods_dir / "test.jar").write_bytes(b"jar")

    response = client.delete(f"/versions/{version}/profiles/{profile.profile_id}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert profile.profile_id not in {p["profile_id"] for p in data["profiles"]}
    assert not version_service.profile_dir(version, profile.profile_id).exists()


def test_delete_default_profile_rejected(client: TestClient, isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    response = client.delete(f"/versions/{version}/profiles/default")
    assert response.status_code == 400


def test_list_profiles_returns_default(client: TestClient, isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    version_service.ensure_profiles_layout(version)

    response = client.get(f"/versions/{version}/profiles")
    assert response.status_code == 200
    data = response.json()
    assert data["active_profile_id"] == "default"
    assert any(profile["profile_id"] == "default" for profile in data["profiles"])


def test_list_profiles_prunes_orphan_dirs(
    client: TestClient,
    isolated_minecraft_versions: Path,
) -> None:
    version = "1.7.10"
    profiles_dir = version_service.profiles_dir(version)
    orphan = profiles_dir / "orphan-recipe-only"
    recipe_dir = orphan / "recipe"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "_export_manifest.json").write_text("{}", encoding="utf-8")

    response = client.get(f"/versions/{version}/profiles")
    assert response.status_code == 200
    profile_ids = {profile["profile_id"] for profile in response.json()["profiles"]}
    assert "orphan-recipe-only" not in profile_ids
    assert not orphan.exists()


def test_list_profiles_resets_missing_active_profile(
    client: TestClient,
    isolated_minecraft_versions: Path,
) -> None:
    version = "1.7.10"
    profiles_dir = version_service.profiles_dir(version)
    from app.services.profile_storage import write_active_profile_id

    write_active_profile_id(profiles_dir, "missing-profile-id")

    response = client.get(f"/versions/{version}/profiles")
    assert response.status_code == 200
    assert response.json()["active_profile_id"] == "default"


def test_import_from_instance_path_prism_minecraft_subfolder(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    """Prism: корень инстанса с пустой mods/ и jar в minecraft/mods/."""
    version = "1.7.10"
    instance = tmp_path / "FTB Infinity"
    (instance / "mods").mkdir(parents=True)
    (instance / "minecraft" / "mods").mkdir(parents=True)
    (instance / "minecraft" / "config").mkdir(parents=True)
    (instance / "minecraft" / "mods" / "IC2.jar").write_bytes(b"jar")
    (instance / "minecraft" / "config" / "ic2.cfg").write_text("x=1", encoding="utf-8")
    mmc = {
        "formatVersion": 1,
        "components": [
            {"uid": "net.minecraft", "version": "1.7.10"},
            {"uid": "net.minecraftforge", "version": "10.13.4.1558"},
        ],
    }
    (instance / "mmc-pack.json").write_text(json.dumps(mmc), encoding="utf-8")

    response = client.post(
        f"/versions/{version}/profiles/import-path",
        json={"path": str(instance), "name": "FTB Infinity"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jars_imported"] == 1
    profile_id = payload["profile"]["profile_id"]
    assert (version_service.mods_dir(version, profile_id) / "IC2.jar").is_file()
    meta = json.loads(
        (version_service.profile_dir(version, profile_id) / "profile.json").read_text(
            encoding="utf-8"
        )
    )
    assert meta.get("forge_version") == "10.13.4.1558"


def test_import_from_instance_path(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    instance = tmp_path / "MyInstance"
    (instance / "mods").mkdir(parents=True)
    (instance / "config").mkdir(parents=True)
    (instance / "mods" / "IC2.jar").write_bytes(b"jar")
    (instance / "config" / "ic2.cfg").write_text("x=1", encoding="utf-8")

    response = client.post(
        f"/versions/{version}/profiles/import-path",
        json={"path": str(instance), "name": "My Instance"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jars_imported"] == 1
    profile_id = payload["profile"]["profile_id"]
    assert (version_service.mods_dir(version, profile_id) / "IC2.jar").is_file()
