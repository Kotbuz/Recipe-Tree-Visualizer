from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.jvm_recipe_export_service import (
    JvmRecipeExportService,
    _LEGACY_FORGE_VERSION,
)


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
    (mods_dir / "IC2Classic-1.7.10-1.2.6.jar").write_bytes(b"fake")

    service = JvmRecipeExportService()
    forge_dir = tmp_path / "forge-runtime" / version
    forge_dir.mkdir(parents=True)
    forge_jar = forge_dir / f"forge-{_LEGACY_FORGE_VERSION}-universal.jar"
    forge_jar.write_bytes(b"fake-forge")
    exporter_jar = tmp_path / "dist" / f"recipe-exporter-{version}.jar"
    exporter_jar.parent.mkdir(parents=True)
    exporter_jar.write_bytes(b"fake-exporter")

    monkeypatch.setattr(service, "_universal_forge_dir", lambda v: forge_dir)
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
