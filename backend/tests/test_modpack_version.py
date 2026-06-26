from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.modpack_version_detector import (
    ModpackVersionInfo,
    detect_forge_from_instance_libraries,
    detect_modpack_version_from_directory,
    detect_modpack_version_from_zip,
    find_modpack_metadata_root,
    forge_installer_version,
    normalize_forge_build,
    normalize_minecraft_version,
)
from app.services.version_service import version_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_normalize_minecraft_version() -> None:
    assert normalize_minecraft_version("1.7.10") == "1.7.10"
    assert normalize_minecraft_version(" 1.16.5 ") == "1.16.5"
    assert normalize_minecraft_version("forge-1.7.10") == "1.7.10"


def test_detect_from_curseforge_manifest_zip(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    manifest = {
        "manifestType": "minecraftModpack",
        "name": "Space Astronomy",
        "minecraft": {
            "version": "1.7.10",
            "modLoaders": [{"id": "forge-10.13.4.1614", "primary": True}],
        },
        "overrides": "overrides",
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/mods/test.jar", b"jar")

    info = detect_modpack_version_from_zip(archive)
    assert info == ModpackVersionInfo(
        minecraft_version="1.7.10",
        modpack_name="Space Astronomy",
        loader="forge",
        forge_version="10.13.4.1614",
        detection_source="manifest.json",
    )


def test_normalize_forge_build() -> None:
    assert normalize_forge_build("10.13.4.1558") == "10.13.4.1558"
    assert normalize_forge_build("52.0.24") == "52.0.24"
    assert normalize_forge_build("1.7.10-10.13.4.1558-1.7.10") == "10.13.4.1558"
    assert normalize_forge_build("1.21.1-52.0.24") == "52.0.24"
    assert forge_installer_version("1.7.10", "10.13.4.1558") == "1.7.10-10.13.4.1558-1.7.10"
    assert forge_installer_version("1.21.1", "52.0.24") == "1.21.1-52.0.24"


def test_detect_from_curseforge_manifest_modern_forge(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    manifest = {
        "manifestType": "minecraftModpack",
        "name": "Modern Pack",
        "minecraft": {
            "version": "1.21.1",
            "modLoaders": [{"id": "forge-52.0.24", "primary": True}],
        },
        "overrides": "overrides",
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/mods/test.jar", b"jar")

    info = detect_modpack_version_from_zip(archive)
    assert info == ModpackVersionInfo(
        minecraft_version="1.21.1",
        modpack_name="Modern Pack",
        loader="forge",
        forge_version="52.0.24",
        detection_source="manifest.json",
    )


def test_detect_forge_from_modern_instance_libraries(tmp_path: Path) -> None:
    lib_dir = (
        tmp_path
        / "libraries"
        / "net"
        / "minecraftforge"
        / "forge"
        / "1.21.1-52.0.24"
    )
    lib_dir.mkdir(parents=True)
    (lib_dir / "forge-1.21.1-52.0.24-server.jar").write_bytes(b"x")

    assert detect_forge_from_instance_libraries(tmp_path) == "52.0.24"


def test_detect_from_mmc_pack_directory(tmp_path: Path) -> None:
    instance = tmp_path / "FTB Infinity"
    (instance / "mods").mkdir(parents=True)
    (instance / "mods" / "test.jar").write_bytes(b"jar")
    mmc = {
        "formatVersion": 1,
        "components": [
            {
                "uid": "net.minecraft",
                "version": "1.7.10",
                "cachedVersion": "1.7.10",
            },
            {
                "uid": "net.minecraftforge",
                "version": "10.13.4.1558",
                "cachedVersion": "10.13.4.1558",
            },
        ],
    }
    (instance / "mmc-pack.json").write_text(json.dumps(mmc), encoding="utf-8")

    info = detect_modpack_version_from_directory(instance)
    assert info == ModpackVersionInfo(
        minecraft_version="1.7.10",
        loader="forge",
        forge_version="10.13.4.1558",
        detection_source="mmc-pack.json",
    )


def test_detect_forge_from_instance_libraries(tmp_path: Path) -> None:
    lib_dir = (
        tmp_path
        / "libraries"
        / "net"
        / "minecraftforge"
        / "forge"
        / "1.7.10-10.13.4.1558-1.7.10"
    )
    lib_dir.mkdir(parents=True)
    (lib_dir / "forge-1.7.10-10.13.4.1558-1.7.10-universal.jar").write_bytes(b"x")

    assert detect_forge_from_instance_libraries(tmp_path) == "10.13.4.1558"


def test_find_modpack_metadata_root_from_minecraft_subfolder(tmp_path: Path) -> None:
    instance = tmp_path / "FTB Infinity"
    (instance / "minecraft" / "mods").mkdir(parents=True)
    mmc = {
        "formatVersion": 1,
        "components": [
            {"uid": "net.minecraft", "version": "1.7.10"},
            {"uid": "net.minecraftforge", "version": "10.13.4.1558"},
        ],
    }
    (instance / "mmc-pack.json").write_text(json.dumps(mmc), encoding="utf-8")

    assert find_modpack_metadata_root(instance / "minecraft") == instance

    info = detect_modpack_version_from_directory(instance / "minecraft")
    assert info is not None
    assert info.forge_version == "10.13.4.1558"


def test_detect_from_instance_cfg_directory(tmp_path: Path) -> None:
    instance = tmp_path / "MyPack"
    (instance / "mods").mkdir(parents=True)
    (instance / "instance.cfg").write_text("InstanceType=One Six\nMCVersion=1.12.2\n", encoding="utf-8")
    (instance / "mods" / "test.jar").write_bytes(b"jar")

    info = detect_modpack_version_from_directory(instance)
    assert info is not None
    assert info.minecraft_version == "1.12.2"
    assert info.detection_source == "instance.cfg"


def test_inspect_modpack_zip_endpoint(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    archive = tmp_path / "pack.zip"
    manifest = {
        "name": "Test Pack",
        "minecraft": {"version": "1.7.10", "modLoaders": [{"id": "forge-10.13.4.1614", "primary": True}]},
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/mods/test.jar", b"jar")

    with archive.open("rb") as handle:
        response = client.post(
            "/modpack/inspect",
            files={"file": ("pack.zip", handle, "application/zip")},
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["minecraft_version"] == "1.7.10"
    assert data["modpack_name"] == "Test Pack"
    assert data["version_installed"] is True


def test_import_modpack_rejects_version_mismatch(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.16.5"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    archive = tmp_path / "pack.zip"
    manifest = {
        "name": "Old Pack",
        "minecraft": {"version": "1.7.10", "modLoaders": [{"id": "forge-10.13.4.1614", "primary": True}]},
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/mods/test.jar", b"jar")

    with archive.open("rb") as handle:
        response = client.post(
            f"/versions/{version}/profiles/import-modpack",
            files={"file": ("pack.zip", handle, "application/zip")},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["detected_version"] == "1.7.10"
    assert detail["requested_version"] == "1.16.5"


def test_import_modpack_allows_matching_version(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    archive = tmp_path / "pack.zip"
    manifest = {
        "name": "Match Pack",
        "minecraft": {"version": "1.7.10", "modLoaders": [{"id": "forge-10.13.4.1614", "primary": True}]},
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/mods/test.jar", b"jar")

    with archive.open("rb") as handle:
        response = client.post(
            f"/versions/{version}/profiles/import-modpack",
            files={"file": ("pack.zip", handle, "application/zip")},
        )
    assert response.status_code == 200, response.text
    assert response.json()["jars_imported"] == 1
    profile_dir = isolated_minecraft_versions / version / "profiles"
    imported = next(path for path in profile_dir.iterdir() if path.is_dir() and path.name != "default")
    meta = json.loads((imported / "profile.json").read_text(encoding="utf-8"))
    assert meta.get("loader") == "forge"
    assert meta.get("forge_version") == "10.13.4.1614"
