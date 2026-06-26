from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.forge_install_service import (
    ForgeInstallService,
    _library_content_valid,
    _read_server_libraries,
    _supports_modern_forge_install,
)
from app.services.version_service import version_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _write_installer_profile(
    installer_path: Path,
    *,
    libraries: list[dict[str, object]],
) -> None:
    profile = {
        "install": {"minecraft": "1.7.10"},
        "versionInfo": {"libraries": libraries},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("install_profile.json", json.dumps(profile))
    installer_path.write_bytes(buffer.getvalue())


def test_forge_install_status_reports_installed(
    client: TestClient,
    isolated_minecraft_versions,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.7.10"
    forge_build = "10.13.4.1558"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    forge_dir = tmp_path / version / forge_build
    forge_dir.mkdir(parents=True)
    (forge_dir / "forge-1.7.10-10.13.4.1558-1.7.10-universal.jar").write_bytes(b"forge")

    service = ForgeInstallService()

    def fake_forge_dir(mc: str, *, forge_build: str | None = None) -> Path:
        return forge_dir

    monkeypatch.setattr(service, "universal_forge_dir", fake_forge_dir)
    monkeypatch.setattr("app.api.routes.versions.forge_install_service", service)

    response = client.get(
        f"/versions/{version}/forge/install-status",
        params={"forge_build": forge_build},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["installed"] is True
    assert data["progress"] == 100


def test_forge_prepare_returns_done_when_already_installed(
    client: TestClient,
    isolated_minecraft_versions,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.7.10"
    forge_build = "10.13.4.1614"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    service = ForgeInstallService()
    monkeypatch.setattr(service, "is_installed", lambda mc, build: True)
    monkeypatch.setattr("app.api.routes.versions.forge_install_service", service)

    response = client.post(
        f"/versions/{version}/forge/prepare",
        json={"forge_build": forge_build},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["installed"] is True
    assert data["phase"] == "done"


def test_read_server_libraries_uses_forge_maven_url() -> None:
    installer_path = Path("installer.jar")
    _write_installer_profile(
        installer_path,
        libraries=[
            {
                "name": "org.scala-lang:scala-xml_2.11:1.0.2",
                "url": "https://maven.minecraftforge.net/",
                "checksums": ["7a80ec00aec122fba7cd4e0d4cdd87ff7e4cb6d0"],
                "serverreq": True,
            }
        ],
    )
    try:
        libraries = _read_server_libraries(installer_path)
        assert len(libraries) == 1
        assert libraries[0].url.endswith(
            "org/scala-lang/scala-xml_2.11/1.0.2/scala-xml_2.11-1.0.2.jar"
        )
        assert libraries[0].checksums == ("7a80ec00aec122fba7cd4e0d4cdd87ff7e4cb6d0",)
    finally:
        installer_path.unlink(missing_ok=True)


def test_bootstrap_redownloads_library_with_invalid_checksum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge_dir = tmp_path / "forge"
    forge_dir.mkdir()
    installer_path = forge_dir / "forge-installer.jar"
    good_jar = b"PK\x03\x04" + (b"good-scala-xml-jar" * 10)
    checksum = hashlib.sha1(good_jar).hexdigest()
    _write_installer_profile(
        installer_path,
        libraries=[
            {
                "name": "org.scala-lang:scala-xml_2.11:1.0.2",
                "url": "https://maven.minecraftforge.net/",
                "checksums": [checksum],
                "serverreq": True,
            }
        ],
    )

    libraries_dir = forge_dir / "libraries"
    destination = (
        libraries_dir
        / "org/scala-lang/scala-xml_2.11/1.0.2/scala-xml_2.11-1.0.2.jar"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"PK\x03\x04" + b"broken")

    service = ForgeInstallService()

    class FakeResponse:
        content = good_jar

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        pass

    def fake_get(
        client: FakeClient,
        url: str,
        *,
        headers: dict[str, str],
    ) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(service, "_http_get_with_retries", fake_get)

    service._bootstrap_forge_installer_libraries(
        forge_dir,
        installer_path,
        FakeClient(),
        lambda phase, message, progress: None,
    )

    assert destination.read_bytes() == good_jar
    assert _library_content_valid(destination.read_bytes(), (checksum,))


def test_supports_modern_forge_install() -> None:
    assert _supports_modern_forge_install("1.21.1")
    assert _supports_modern_forge_install("1.22")
    assert not _supports_modern_forge_install("1.7.10")
    assert not _supports_modern_forge_install("1.20.1")


def test_forge_install_status_reports_modern_server_jar(
    client: TestClient,
    isolated_minecraft_versions,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.21.1"
    forge_build = "52.0.24"
    forge_version = "1.21.1-52.0.24"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    forge_dir = tmp_path / version / forge_build
    server_jar = (
        forge_dir
        / "libraries"
        / "net"
        / "minecraftforge"
        / "forge"
        / forge_version
        / f"forge-{forge_version}-server.jar"
    )
    server_jar.parent.mkdir(parents=True)
    server_jar.write_bytes(b"forge-server")

    service = ForgeInstallService()

    def fake_forge_dir(mc: str, *, forge_build: str | None = None) -> Path:
        return forge_dir

    monkeypatch.setattr(service, "universal_forge_dir", fake_forge_dir)
    monkeypatch.setattr("app.api.routes.versions.forge_install_service", service)

    response = client.get(
        f"/versions/{version}/forge/install-status",
        params={"forge_build": forge_build},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["installed"] is True
    assert data["progress"] == 100


def test_forge_prepare_accepts_modern_version(
    client: TestClient,
    isolated_minecraft_versions,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.21.1"
    forge_build = "52.0.24"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    service = ForgeInstallService()
    monkeypatch.setattr(service, "is_installed", lambda mc, build: True)
    monkeypatch.setattr("app.api.routes.versions.forge_install_service", service)

    response = client.post(
        f"/versions/{version}/forge/prepare",
        json={"forge_build": forge_build},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["installed"] is True
    assert data["phase"] == "done"


def test_forge_prepare_rejects_unsupported_version(
    client: TestClient,
    isolated_minecraft_versions,
) -> None:
    version = "1.20.1"
    version_service.ensure_version_layout(version)
    version_service.client_jar_path(version).write_bytes(b"x" * 2048)

    response = client.post(
        f"/versions/{version}/forge/prepare",
        json={"forge_build": "47.1.0"},
    )
    assert response.status_code == 422, response.text
    assert "1.21" in response.json()["detail"]
