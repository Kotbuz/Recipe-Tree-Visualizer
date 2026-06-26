from pathlib import Path

import pytest

from app.services.mod_service import ModNotFoundError, mod_service

pytestmark = pytest.mark.usefixtures("isolated_minecraft_versions")


def test_delete_mod_jar_removes_file_and_registry(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    mods_dir = isolated_minecraft_versions / version / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    keep = mods_dir / "keep.jar"
    remove = mods_dir / "remove-me.jar"
    keep.write_bytes(b"keep")
    remove.write_bytes(b"remove")

    mod_service.force_reload_version(version)
    assert len(mod_service.list_mods(version)) == 2

    summaries = mod_service.delete_mod_jar(version, "remove-me.jar")

    assert not remove.exists()
    assert keep.is_file()
    assert len(summaries) == 1
    assert summaries[0].jar_filename == "keep.jar"


def test_delete_mod_jar_missing_raises(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    with pytest.raises(ModNotFoundError):
        mod_service.delete_mod_jar(version, "missing.jar")
