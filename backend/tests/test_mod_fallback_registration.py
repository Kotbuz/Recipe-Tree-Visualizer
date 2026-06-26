import zipfile
from pathlib import Path

import pytest

from app.services.mod_service import mod_service

pytestmark = pytest.mark.usefixtures("isolated_minecraft_versions")


def test_scan_registers_unparseable_jar_with_fallback(
    isolated_minecraft_versions: Path,
) -> None:
    version = "1.7.10"
    mods_dir = isolated_minecraft_versions / version / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    jar_path = mods_dir / "CodeChickenCore-1.4.16.jar"
    jar_path.write_bytes(b"not a jar")

    summaries = mod_service.force_reload_version(version)

    assert len(summaries) == 1
    assert summaries[0].mod_id == "codechickencore"
    assert summaries[0].jar_filename == jar_path.name


def test_scan_registers_library_jar_without_mcmod_info(
    isolated_minecraft_versions: Path,
) -> None:
    version = "1.7.10"
    mods_dir = isolated_minecraft_versions / version / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    jar_path = mods_dir / "CodeChickenCore-1.4.16.jar"
    with zipfile.ZipFile(jar_path, "w") as archive:
        archive.writestr("dummy.txt", "no metadata")

    summaries = mod_service.force_reload_version(version)

    assert len(summaries) == 1
    assert summaries[0].mod_id == "codechickencore"
    assert summaries[0].recipe_count == 0
