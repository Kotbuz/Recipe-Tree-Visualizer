import pytest

from app.recipes.manager import recipe_manager
from app.recipes.providers.vanilla_jar import VanillaJarProvider
from app.services.version_service import version_service


@pytest.mark.usefixtures("isolated_minecraft_versions")
def test_jvm_export_directory_reads_recipe_id(isolated_minecraft_versions) -> None:
    version = "1.7.10"
    recipe_dir = version_service.recipe_dir(version)
    (recipe_dir / "_export_manifest.json").write_text("{}", encoding="utf-8")
    (recipe_dir / "ic2__export__crafting__0.json").write_text(
        """
        {
          "id": "ic2:export/crafting/0",
          "type": "crafting_shaped",
          "pattern": ["#"],
          "key": {"#": {"item": "minecraft:iron_ingot"}},
          "result": {"item": "ic2:machine"}
        }
        """,
        encoding="utf-8",
    )

    recipe_manager._clear_caches()
    result = VanillaJarProvider().load(version)

    assert len(result.recipes) == 1
    assert result.recipes[0].id == "ic2:export/crafting/0"
    assert result.recipes[0].mod_id == "ic2"
