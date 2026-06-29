from pathlib import Path

import pytest
from app.parser.jar_reader import JarReader
from app.recipes.manager import recipe_manager
from app.recipes.providers.mod_jar import ModJarProvider
from app.services.mod_service import mod_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"
STORAGE_DRAWERS_JAR = (
    Path(__file__).parent / "fixtures" / "StorageDrawers-fabric-1.21.11-20.0.0.jar"
)

pytestmark = pytest.mark.usefixtures("isolated_minecraft_versions")


def test_mod_jar_provider_loads_natures_compass() -> None:
    provider = ModJarProvider()
    result = provider.load(str(NATURES_COMPASS_JAR))

    assert len(result.recipes) == 2
    assert result.skipped == []

    shaped = next(
        recipe for recipe in result.recipes if recipe.id == "naturescompass:natures_compass"
    )
    assert shaped.mod_id == "naturescompass"
    assert shaped.source == "mod:naturescompass"
    assert {part.item_id: part.amount for part in shaped.inputs} == {
        "tag:saplings": 4.0,
        "tag:logs": 4.0,
        "minecraft:compass": 1.0,
    }


def test_mod_jar_provider_skips_unsupported_types() -> None:
    provider = ModJarProvider()
    result = provider.load(str(STORAGE_DRAWERS_JAR))

    assert len(result.recipes) == 127
    assert len(result.skipped) == 5


def test_recipe_manager_merges_mod_recipes() -> None:
    raw = JarReader().read(str(NATURES_COMPASS_JAR))
    recipe_manager.load_mod_jar(str(NATURES_COMPASS_JAR), meta=raw.meta, storage_version="26.2")

    merged = recipe_manager.get_version_recipes("26.2", include_mods=True)
    mod_recipe_ids = {recipe.id for recipe in recipe_manager.get_mod_recipes()}

    assert any(recipe.id in mod_recipe_ids for recipe in merged)

    vanilla_only = recipe_manager.get_version_recipes("26.2", include_mods=False)
    assert all(recipe.id not in mod_recipe_ids for recipe in vanilla_only)


def test_mod_service_registers_recipes_in_manager() -> None:
    mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)], "26.2")

    assert any(
        recipe.id == "naturescompass:natures_compass" for recipe in recipe_manager.get_mod_recipes()
    )

    summaries = recipe_manager.search_summaries(
        "26.2",
        produces_item="naturescompass:naturescompass",
        limit=10,
        include_mods=True,
    )
    assert summaries
    assert any(recipe.recipe_id == "naturescompass:natures_compass" for recipe in summaries)


def test_search_without_mods_excludes_uploaded_recipes() -> None:
    mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)], "26.2")

    with_mods = recipe_manager.search_summaries(
        "26.2",
        produces_item="naturescompass:naturescompass",
        limit=10,
        include_mods=True,
    )
    without_mods = recipe_manager.search_summaries(
        "26.2",
        produces_item="naturescompass:naturescompass",
        limit=10,
        include_mods=False,
    )

    assert with_mods
    assert without_mods == []
