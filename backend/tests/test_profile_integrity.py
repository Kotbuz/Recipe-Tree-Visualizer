from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.profile_storage import read_profile_meta, write_profile_meta
from app.services.version_service import version_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _write_instance_with_kubejs(instance: Path) -> None:
    (instance / "minecraft" / "mods").mkdir(parents=True)
    (instance / "minecraft" / "mods" / "mod-a.jar").write_bytes(b"jar-a")
    (instance / "minecraft" / "mods" / "mod-b.jar").write_bytes(b"jar-b")
    kubejs = instance / "minecraft" / "kubejs"
    (kubejs / "server_scripts" / "custom_machinery").mkdir(parents=True)
    (kubejs / "server_scripts" / "crafting.js").write_text("// crafting", encoding="utf-8")
    (kubejs / "server_scripts" / "custom_machinery" / "recycle.js").write_text(
        "// cm",
        encoding="utf-8",
    )


def test_integrity_detects_missing_kubejs_and_sync_restores(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    instance = tmp_path / "Techopolis"
    _write_instance_with_kubejs(instance)

    response = client.post(
        f"/versions/{version}/profiles/import-path",
        json={"path": str(instance), "name": "Techopolis Integrity"},
    )
    assert response.status_code == 200, response.text
    profile_id = response.json()["profile"]["profile_id"]
    profile_dir = version_service.profile_dir(version, profile_id)

    import shutil

    shutil.rmtree(profile_dir / "kubejs")
    (profile_dir / "mods" / "mod-b.jar").unlink(missing_ok=True)

    integrity = client.get(f"/versions/{version}/profiles/{profile_id}/integrity")
    assert integrity.status_code == 200, integrity.text
    payload = integrity.json()
    assert payload["healthy"] is False
    assert payload["can_sync"] is True
    assert any(issue["category"] == "kubejs" and issue["missing_count"] > 0 for issue in payload["issues"])
    assert any(issue["category"] == "mods" and issue["missing_count"] > 0 for issue in payload["issues"])

    sync = client.post(f"/versions/{version}/profiles/{profile_id}/sync")
    assert sync.status_code == 200, sync.text
    sync_payload = sync.json()
    assert sync_payload["kubejs_server_scripts_synced"] >= 2
    assert sync_payload["jars_synced"] >= 1
    assert sync_payload["integrity"]["healthy"] is True

    kubejs_dir = version_service.kubejs_dir(version, profile_id)
    assert (kubejs_dir / "server_scripts" / "crafting.js").is_file()
    assert (kubejs_dir / "server_scripts" / "custom_machinery" / "recycle.js").is_file()
    assert (profile_dir / "mods" / "mod-b.jar").is_file()


def test_integrity_accepts_source_path_override(
    client: TestClient,
    isolated_minecraft_versions: Path,
    tmp_path: Path,
) -> None:
    version = "1.7.10"
    instance = tmp_path / "Techopolis"
    _write_instance_with_kubejs(instance)

    response = client.post(
        f"/versions/{version}/profiles/import-path",
        json={"path": str(instance), "name": "Techopolis Override"},
    )
    assert response.status_code == 200, response.text
    profile_id = response.json()["profile"]["profile_id"]
    profile_dir = version_service.profile_dir(version, profile_id)
    meta = read_profile_meta(profile_dir)
    assert meta.get("source_path") == str(instance)

    import shutil

    shutil.rmtree(profile_dir / "kubejs")

    moved = tmp_path / "TechopolisMoved"
    shutil.move(str(instance), str(moved))

    integrity = client.get(
        f"/versions/{version}/profiles/{profile_id}/integrity",
        params={"source_path": str(moved)},
    )
    assert integrity.status_code == 200, integrity.text
    payload = integrity.json()
    assert payload["source_available"] is True
    assert payload["needs_source_path"] is False
    assert payload["can_sync"] is True

    sync = client.post(
        f"/versions/{version}/profiles/{profile_id}/sync",
        json={"path": str(moved)},
    )
    assert sync.status_code == 200, sync.text
    assert sync.json()["kubejs_server_scripts_synced"] >= 2
    assert sync.json()["integrity"]["healthy"] is True


def test_integrity_reports_unavailable_source_for_manual_profile(
    client: TestClient,
    isolated_minecraft_versions: Path,
) -> None:
    version = "1.7.10"
    profile_dir = version_service.profile_dir(version, "manual-pack")
    profile_dir.mkdir(parents=True, exist_ok=True)
    write_profile_meta(
        profile_dir,
        profile_id="manual-pack",
        name="Manual",
        source="manual",
    )

    response = client.get(f"/versions/{version}/profiles/manual-pack/integrity")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_available"] is False
    assert payload["can_sync"] is False
    assert payload["healthy"] is False
