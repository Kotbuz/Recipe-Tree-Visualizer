import shutil
from pathlib import Path

import pytest

from app.recipes.loaders.recipe_paths import recipe_layout_for_version
from app.services.jvm_recipe_export_service import JvmRecipeExportError, JvmRecipeExportService
from app.services.mod_service import mod_service
from app.services.version_service import version_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"

pytestmark = pytest.mark.usefixtures("isolated_minecraft_versions")


def test_force_reload_version_picks_up_new_jars(isolated_minecraft_versions: Path) -> None:
    version = "26.2"
    mods_dir = version_service.mods_dir(version)
    shutil.copy(NATURES_COMPASS_JAR, mods_dir / NATURES_COMPASS_JAR.name)

    mod_service.ensure_version_mods_loaded(version)
    assert len(mod_service.list_mods(version)) == 1

    shutil.copy(NATURES_COMPASS_JAR, mods_dir / "second-copy.jar")
    summaries = mod_service.force_reload_version(version)
    assert len(summaries) == 2


def test_clear_exported_recipes_removes_files(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    service = JvmRecipeExportService()
    recipe_dir = version_service.recipe_dir(version)
    (recipe_dir / "minecraft__export__crafting__0.json").write_text("{}", encoding="utf-8")
    (recipe_dir / "_export_manifest.json").write_text("{}", encoding="utf-8")
    (version_service._version_dir(version) / "ore_dict.json").write_text("{}", encoding="utf-8")

    deleted, ore_dict_removed = service.clear_exported_recipes(version)
    assert deleted == 2
    assert ore_dict_removed is True
    assert list(recipe_dir.glob("*.json")) == []
    assert not (version_service._version_dir(version) / "ore_dict.json").exists()


def test_clear_exported_recipes_rejects_non_jvm_layout() -> None:
    version = "26.2"
    assert recipe_layout_for_version(version) != "jvm"
    with pytest.raises(JvmRecipeExportError):
        JvmRecipeExportService().clear_exported_recipes(version)
