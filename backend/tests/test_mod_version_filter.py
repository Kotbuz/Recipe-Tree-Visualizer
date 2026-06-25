from pathlib import Path

from app.parser.jar_reader import JarReader
from app.parser.minecraft_version import mod_supports_game_version, version_in_constraint
from app.recipes.manager import recipe_manager
from app.services.mod_service import mod_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"
CREATE_JAR = Path(__file__).parent.parent / "data" / "mods" / "create-1.18.2-0.5.0.e.jar"
STORAGE_DRAWERS_JAR = (
    Path(__file__).parent / "fixtures" / "StorageDrawers-fabric-1.21.11-20.0.0.jar"
)


def test_version_in_constraint_bracket_and_fabric() -> None:
    assert version_in_constraint("[26.2]", "26.2")
    assert not version_in_constraint("[26.2]", "1.18.2")
    assert version_in_constraint("[1.18.2,1.19)", "1.18.2")
    assert not version_in_constraint("[1.18.2,1.19)", "1.19")
    assert version_in_constraint(">=1.21.11 <1.21.12", "1.21.11")
    assert not version_in_constraint(">=1.21.11 <1.21.12", "1.21.12")


def test_mod_supports_game_version_from_metadata() -> None:
    natures = JarReader().read(str(NATURES_COMPASS_JAR)).meta
    assert mod_supports_game_version(
        minecraft_version=natures.minecraft_version,
        minecraft_version_range=natures.minecraft_version_range,
        jar_path=NATURES_COMPASS_JAR.name,
        game_version="26.2",
    )
    assert not mod_supports_game_version(
        minecraft_version=natures.minecraft_version,
        minecraft_version_range=natures.minecraft_version_range,
        jar_path=NATURES_COMPASS_JAR.name,
        game_version="1.18.2",
    )


def test_recipe_manager_filters_mods_by_game_version() -> None:
    if not CREATE_JAR.is_file():
        return

    create_raw = JarReader().read(str(CREATE_JAR))
    natures_raw = JarReader().read(str(NATURES_COMPASS_JAR))
    recipe_manager.load_mod_jar(str(CREATE_JAR), meta=create_raw.meta)
    recipe_manager.load_mod_jar(str(NATURES_COMPASS_JAR), meta=natures_raw.meta)

    recipes_26 = recipe_manager.get_version_recipes("26.2", include_mods=True)
    recipes_18 = recipe_manager.get_version_recipes("1.18.2", include_mods=True)

    mod_ids_26 = {recipe.mod_id for recipe in recipes_26 if recipe.source.startswith("mod:")}
    mod_ids_18 = {recipe.mod_id for recipe in recipes_18 if recipe.source.startswith("mod:")}

    assert "naturescompass" in mod_ids_26
    assert "create" not in mod_ids_26
    assert "create" in mod_ids_18
    assert "naturescompass" not in mod_ids_18


def test_mod_service_marks_compatibility_for_selected_version() -> None:
    mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)])

    compatible = mod_service.list_mods(game_version="26.2")
    incompatible = mod_service.list_mods(game_version="1.18.2")

    assert compatible[0].compatible is True
    assert incompatible[0].compatible is False


def test_storage_drawers_only_for_matching_version() -> None:
    raw = JarReader().read(str(STORAGE_DRAWERS_JAR))
    recipe_manager.load_mod_jar(str(STORAGE_DRAWERS_JAR), meta=raw.meta)

    drawers_recipes = {
        recipe.id
        for recipe in recipe_manager.get_version_recipes("1.21.11", include_mods=True)
        if recipe.mod_id == "storagedrawers"
    }
    missing_on_26 = {
        recipe.id
        for recipe in recipe_manager.get_version_recipes("26.2", include_mods=True)
        if recipe.mod_id == "storagedrawers"
    }

    assert drawers_recipes
    assert not missing_on_26
