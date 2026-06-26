from pathlib import Path

import pytest

from app.parser.recipe_types import SMELTING
from app.recipes.loaders.ae2_recipe_loader import load_ae2_recipe_directory
from app.recipes.manager import recipe_manager
from app.recipes.providers.vanilla_jar import VanillaJarProvider


def test_load_ae2_smelt_and_processor_recipes(
    isolated_minecraft_versions,
) -> None:
    from app.recipes.adapters import to_recipe_summary
    from app.recipes.loaders.item_catalog_loader import load_item_catalog

    version = "1.7.10"
    version_root = isolated_minecraft_versions / version
    (version_root / "ore_dict.json").write_text(
        """
        {
          "dustNetherQuartz": {
            "item": "appliedenergistics2:item.ItemMultiMaterial",
            "metadata": 3
          },
          "itemSilicon": {
            "item": "appliedenergistics2:item.ItemMultiMaterial",
            "metadata": 5
          }
        }
        """,
        encoding="utf-8",
    )
    recipe_dir = version_root / "recipe" / "ae2-recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    (recipe_dir / "processing").mkdir(parents=True, exist_ok=True)
    (recipe_dir / "processing" / "vanilla.recipe").write_text(
        "smelt= ae2:ItemMaterial.NetherQuartzDust -> ae2:ItemMaterial.Silicon\n",
        encoding="utf-8",
    )
    (recipe_dir / "processing" / "grind.recipe").write_text(
        "grind= mc:quartz -> ae2:ItemMaterial.NetherQuartzDust\n",
        encoding="utf-8",
    )

    load_item_catalog.cache_clear()
    result = load_ae2_recipe_directory(recipe_dir, version=version)
    assert len(result.recipes) == 2

    smelt = next(recipe for recipe in result.recipes if recipe.raw_type == SMELTING)
    assert smelt.inputs[0].metadata == 3
    assert smelt.outputs[0].metadata == 5

    grind = next(recipe for recipe in result.recipes if recipe.raw_type == "ae2:grind")
    assert grind.inputs[0].item_id == "minecraft:quartz"
    assert grind.outputs[0].metadata == 3

    summary = to_recipe_summary(smelt, version=version)
    assert summary.outputs[0].name == "Silicon"
    assert summary.inputs[0].name == "Nether Quartz Dust"


def test_load_ae2_shaped_recipe_from_fixture(isolated_minecraft_versions) -> None:
    version = "1.7.10"
    version_root = isolated_minecraft_versions / version
    (version_root / "ore_dict.json").write_text(
        """
        {
          "crystalCertusQuartz": {
            "item": "appliedenergistics2:item.ItemMultiMaterial",
            "metadata": 0
          },
          "stickWood": "minecraft:stick"
        }
        """,
        encoding="utf-8",
    )

    recipe_dir = version_root / "recipe" / "ae2-recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    (recipe_dir / "oredict.recipe").write_text(
        "ore=ae2:ItemMaterial.CertusQuartzCrystal -> crystalCertusQuartz\n",
        encoding="utf-8",
    )
    (recipe_dir / "tools.certus-quartz.recipe").write_text(
        """
        shaped=
            oredictionary:crystalCertusQuartz oredictionary:crystalCertusQuartz,
            oredictionary:crystalCertusQuartz oredictionary:stickWood,
            _ oredictionary:stickWood
            -> ae2:ToolCertusQuartzAxe
        """,
        encoding="utf-8",
    )

    result = load_ae2_recipe_directory(recipe_dir, version=version)
    assert len(result.recipes) == 1
    recipe = result.recipes[0]
    assert recipe.mod_id == "appliedenergistics2"
    assert recipe.outputs[0].item_id == "appliedenergistics2:item.ToolCertusQuartzAxe"
    assert len(recipe.inputs) == 2
    assert sum(part.amount for part in recipe.inputs) == 5
    assert any(part.metadata == 0 for part in recipe.inputs)


def test_load_ae2_item_part_recipe_uses_display_names(
    isolated_minecraft_versions,
) -> None:
    from app.recipes.adapters import to_recipe_summary

    version = "1.7.10"
    version_root = isolated_minecraft_versions / version
    (version_root / "ore_dict.json").write_text("{}", encoding="utf-8")
    recipe_dir = version_root / "recipe" / "ae2-recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    (recipe_dir / "interfaces.recipe").write_text(
        """
        shapeless=
            ae2:ItemPart.Interface
            -> ae2:BlockInterface
        """,
        encoding="utf-8",
    )

    result = load_ae2_recipe_directory(recipe_dir, version=version)
    assert len(result.recipes) == 1
    recipe = result.recipes[0]
    assert recipe.inputs[0].item_id == "appliedenergistics2:item.Interface"
    summary = to_recipe_summary(recipe, version=version)
    assert summary.inputs[0].name != "item.ItemMultiPart"
    assert "interface" in summary.inputs[0].name.lower()


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath(
        "../MinecraftVersions/1.7.10/mods"
    ).glob("*appliedenergistics2*.jar"),
    reason="AE2 mod jar not available",
)
def test_load_ae2_item_part_recipe_resolves_lang_display_name() -> None:
    from app.recipes.adapters import to_recipe_summary
    from app.recipes.loaders.item_catalog_loader import load_item_catalog

    load_item_catalog.cache_clear()

    repo_root = Path(__file__).resolve().parents[2]
    ae2_root = (
        repo_root
        / "recipe-exporter"
        / "forge-runtime"
        / "1.7.10"
        / "config"
        / "AppliedEnergistics2"
        / "recipes"
        / "generated"
        / "network"
        / "blocks"
        / "interfaces.recipe"
    )
    if not ae2_root.is_file():
        pytest.skip("AE2 interfaces recipe not available")

    result = load_ae2_recipe_directory(ae2_root.parent.parent.parent, version="1.7.10")
    interface_recipes = [
        recipe
        for recipe in result.recipes
        if any(part.item_id.endswith(":item.Interface") for part in recipe.inputs)
    ]
    assert interface_recipes
    recipe = interface_recipes[0]
    part = next(part for part in recipe.inputs if part.item_id.endswith(":item.Interface"))
    summary = to_recipe_summary(recipe, version="1.7.10")
    interface_name = next(item.name for item in summary.inputs if item.item_id.endswith(":item.Interface"))
    assert "interface" in interface_name.lower()


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath(
        "../recipe-exporter/forge-runtime/1.7.10/config/AppliedEnergistics2/recipes/generated"
    ).is_dir(),
    reason="AE2 generated recipes not available",
)
def test_load_ae2_recipes_from_forge_runtime() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ae2_root = (
        repo_root
        / "recipe-exporter"
        / "forge-runtime"
        / "1.7.10"
        / "config"
        / "AppliedEnergistics2"
        / "recipes"
        / "generated"
    )
    result = load_ae2_recipe_directory(ae2_root.parent.parent.parent, version="1.7.10")
    assert len(result.recipes) >= 250
    assert all(recipe.mod_id == "appliedenergistics2" for recipe in result.recipes)


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath(
        "../MinecraftVersions/1.7.10/recipe"
    ).is_dir(),
    reason="1.7.10 recipe export not available",
)
def test_vanilla_provider_merges_exported_ae2_recipes(
    isolated_minecraft_versions,
) -> None:
    from app.services.jvm_recipe_export_service import jvm_recipe_export_service

    version = "1.7.10"
    jvm_recipe_export_service.ensure_ae2_recipes_synced(version)
    recipe_manager._clear_caches()
    result = VanillaJarProvider().load(version)
    ae2_recipes = [recipe for recipe in result.recipes if recipe.mod_id == "appliedenergistics2"]
    assert len(ae2_recipes) >= 200
