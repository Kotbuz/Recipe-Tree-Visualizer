import zipfile
from pathlib import Path

from app.parser.jar_reader import JarReader


def test_infer_ic2_classic_from_package_namespace(tmp_path: Path) -> None:
    jar_path = tmp_path / "IC2Classic-1.7.10-1.2.5.jar"
    with zipfile.ZipFile(jar_path, "w") as archive:
        archive.writestr("ic2classic/core/Mod.class", b"")

    meta = JarReader().read(str(jar_path)).meta

    assert meta.mod_id == "ic2"
    assert meta.name == "IC2 Classic"


def test_infer_ic2_classic_from_filename_when_no_metadata(tmp_path: Path) -> None:
    jar_path = tmp_path / "IC2Classic-1.7.10-1.2.5.jar"
    with zipfile.ZipFile(jar_path, "w") as archive:
        archive.writestr("dummy.txt", "no metadata")

    meta = JarReader().read(str(jar_path)).meta

    assert meta.mod_id == "ic2"
    assert meta.name == "IC2 Classic"
