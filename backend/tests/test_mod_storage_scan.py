import shutil
from pathlib import Path

import pytest

from app.services.mod_service import mod_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"
IC2_JAR = Path(__file__).parent.parent / "data" / "mods" / "industrialcraft-2-2.8.222-ex112.jar"

pytestmark = pytest.mark.usefixtures("isolated_minecraft_versions")


def test_scan_storage_mods_loads_fixture_jar(isolated_minecraft_versions: Path) -> None:
    version = "26.2"
    mods_dir = isolated_minecraft_versions / version / "mods"
    shutil.copy(NATURES_COMPASS_JAR, mods_dir / NATURES_COMPASS_JAR.name)

    summaries = mod_service.scan_storage_mods(version)

    assert len(summaries) == 1
    assert summaries[0].mod_id == "naturescompass"
    assert summaries[0].recipe_count >= 1


def test_mcmod_info_legacy_metadata() -> None:
    if not IC2_JAR.is_file():
        return

    summary = mod_service.upload_mods_from_paths([str(IC2_JAR)], "1.12.2")[0]

    assert summary.mod_id == "ic2"
    assert summary.name == "IndustrialCraft 2"
    assert summary.loader == "forge"
    assert summary.recipe_count == 0
