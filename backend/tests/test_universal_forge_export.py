from pathlib import Path
from unittest.mock import MagicMock, patch
import io
import zipfile

import json
import pytest

from app.services.jvm_recipe_export_service import (
    JvmRecipeExportService,
    _LEGACY_FORGE_VERSION,
)


def _write_minimal_jar(path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    path.write_bytes(buffer.getvalue())


def test_universal_forge_export_uses_profile_forge_build(
    isolated_minecraft_versions: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.7.10"
    profile_id = "pack-test"
    version_dir = isolated_minecraft_versions / version
    profile_dir = version_dir / "profiles" / profile_id
    recipe_dir = profile_dir / "recipe"
    mods_dir = profile_dir / "mods"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "client.jar").write_bytes(b"fake")
    _write_minimal_jar(mods_dir / "IC2Classic-1.7.10-1.2.6.jar")
    (profile_dir / "profile.json").write_text(
        json.dumps(
            {
                "profile_id": profile_id,
                "name": "Test",
                "source": "instance_path",
                "created_at": "2026-01-01T00:00:00+00:00",
                "loader": "forge",
                "forge_version": "10.13.4.1558",
            }
        ),
        encoding="utf-8",
    )

    service = JvmRecipeExportService()
    forge_dir = tmp_path / "forge-runtime" / version / "10.13.4.1558"
    forge_dir.mkdir(parents=True)
    forge_jar = forge_dir / "forge-1.7.10-10.13.4.1558-1.7.10-universal.jar"
    forge_jar.write_bytes(b"fake-forge")
    exporter_jar = tmp_path / "dist" / f"recipe-exporter-{version}.jar"
    exporter_jar.parent.mkdir(parents=True)
    exporter_jar.write_bytes(b"fake-exporter")

    monkeypatch.setattr(
        "app.services.jvm_recipe_export_service.forge_install_service.ensure_installed",
        lambda version, forge_build=None: forge_jar,
    )
    monkeypatch.setattr(service, "_resolve_exporter_jar", lambda v: exporter_jar)

    with patch("app.services.jvm_recipe_export_service.subprocess.run") as run_mock:
        run_mock.return_value = MagicMock(stdout="", stderr="")
        service._run_universal_forge_export(
            version,
            mods_dir=mods_dir,
            recipe_dir=recipe_dir,
            version_dir=version_dir,
            forge_build="10.13.4.1558",
        )

    command = run_mock.call_args.args[0]
    assert str(forge_jar) in command


def test_universal_forge_export_invokes_production_forge(
    isolated_minecraft_versions: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.7.10"
    version_dir = isolated_minecraft_versions / version
    recipe_dir = version_dir / "recipe"
    mods_dir = version_dir / "mods"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "client.jar").write_bytes(b"fake")
    _write_minimal_jar(mods_dir / "IC2Classic-1.7.10-1.2.6.jar")

    service = JvmRecipeExportService()
    forge_dir = tmp_path / "forge-runtime" / version
    forge_dir.mkdir(parents=True)
    forge_jar = forge_dir / f"forge-{_LEGACY_FORGE_VERSION}-universal.jar"
    forge_jar.write_bytes(b"fake-forge")
    exporter_jar = tmp_path / "dist" / f"recipe-exporter-{version}.jar"
    exporter_jar.parent.mkdir(parents=True)
    exporter_jar.write_bytes(b"fake-exporter")

    monkeypatch.setattr(
        "app.services.jvm_recipe_export_service.forge_install_service.ensure_installed",
        lambda version, forge_build=None: forge_jar,
    )
    monkeypatch.setattr(service, "_resolve_exporter_jar", lambda v: exporter_jar)

    with patch("app.services.jvm_recipe_export_service.subprocess.run") as run_mock:
        run_mock.return_value = MagicMock(stdout="", stderr="")
        exported = service._run_universal_forge_export(
            version,
            mods_dir=mods_dir,
            recipe_dir=recipe_dir,
            version_dir=version_dir,
        )

    assert exported == 0
    command = run_mock.call_args.args[0]
    assert str(forge_jar) in command
    assert "-Drtv.recipe.export=true" in command
    assert (forge_dir / "mods" / exporter_jar.name).is_file()
    assert (forge_dir / "mods" / "IC2Classic-1.7.10-1.2.6.jar").is_file()
    assert "-Djava.awt.headless=true" in command


def test_should_skip_forge_export_mod() -> None:
    service = JvmRecipeExportService()
    assert service._should_skip_forge_export_mod(
        "ForgeMicroblock-1.7.10-1.2.0.347-universal.jar"
    )
    assert not service._should_skip_forge_export_mod(
        "ForgeMultipart-1.7.10-1.2.0.347-universal.jar"
    )
    assert service._should_skip_forge_export_mod("commons-compress-1.8.1.jar")
    assert not service._should_skip_forge_export_mod("IC2Classic-1.7.10-1.2.6.jar")
    assert service._is_client_only_forge_export_mod(
        "ResourceLoader-MC1.7.10-1.3.jar"
    )
    assert service._is_client_only_forge_export_mod(
        "CustomMainMenu-MC1.7.10-1.9.2.jar"
    )


def test_universal_forge_export_skips_deploader_problem_mods(
    isolated_minecraft_versions: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "1.7.10"
    version_dir = isolated_minecraft_versions / version
    recipe_dir = version_dir / "recipe"
    mods_dir = version_dir / "mods"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "client.jar").write_bytes(b"fake")
    _write_minimal_jar(mods_dir / "ForgeMultipart-1.7.10-1.2.0.347-universal.jar")
    _write_minimal_jar(mods_dir / "ForgeMicroblock-1.7.10-1.2.0.347-universal.jar")
    _write_minimal_jar(mods_dir / "IC2Classic-1.7.10-1.2.6.jar")

    service = JvmRecipeExportService()
    forge_dir = tmp_path / "forge-runtime" / version
    forge_dir.mkdir(parents=True)
    forge_jar = forge_dir / f"forge-{_LEGACY_FORGE_VERSION}-universal.jar"
    forge_jar.write_bytes(b"fake-forge")
    exporter_jar = tmp_path / "dist" / f"recipe-exporter-{version}.jar"
    exporter_jar.parent.mkdir(parents=True)
    exporter_jar.write_bytes(b"fake-exporter")

    monkeypatch.setattr(
        "app.services.jvm_recipe_export_service.forge_install_service.ensure_installed",
        lambda version, forge_build=None: forge_jar,
    )
    monkeypatch.setattr(service, "_resolve_exporter_jar", lambda v: exporter_jar)

    with patch("app.services.jvm_recipe_export_service.subprocess.run") as run_mock:
        run_mock.return_value = MagicMock(stdout="", stderr="")
        service._run_universal_forge_export(
            version,
            mods_dir=mods_dir,
            recipe_dir=recipe_dir,
            version_dir=version_dir,
        )

    assert (forge_dir / "mods" / "ForgeMultipart-1.7.10-1.2.0.347-universal.jar").is_file()
    assert not (
        forge_dir / "mods" / "ForgeMicroblock-1.7.10-1.2.0.347-universal.jar"
    ).exists()
    assert (forge_dir / "mods" / "IC2Classic-1.7.10-1.2.6.jar").is_file()
