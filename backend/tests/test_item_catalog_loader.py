from pathlib import Path

import pytest
from app.recipes.adapters import to_recipe_summary
from app.recipes.loaders.ae2_recipe_loader import load_ae2_recipe_directory
from app.recipes.loaders.item_catalog_loader import (
    load_item_catalog,
    resolve_catalog_display_name,
)
from app.recipes.manager import recipe_manager
from app.recipes.registry import get_version_ingredient_registry


def test_item_catalog_resolves_certus_quartz_display_name() -> None:
    load_item_catalog.cache_clear()
    name = resolve_catalog_display_name(
        "appliedenergistics2:item.ItemMultiMaterial",
        0,
        version="1.7.10",
    )
    assert name is not None
    assert "certus" in name.lower()


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath("../MinecraftVersions/1.7.10/mods").is_dir(),
    reason="1.7.10 mods not available",
)
def test_item_catalog_resolves_ae2_cable_display_names() -> None:
    from app.recipes.loaders.item_catalog_loader import (
        _parse_ae2_lang,
        resolve_ae2_composite_display_name,
    )

    load_item_catalog.cache_clear()
    _parse_ae2_lang.cache_clear()

    fluix = resolve_ae2_composite_display_name(
        "appliedenergistics2:item.CableCovered.Fluix",
        version="1.7.10",
    )
    white = resolve_ae2_composite_display_name(
        "appliedenergistics2:item.CableSmart.White",
        version="1.7.10",
    )
    paint = resolve_ae2_composite_display_name(
        "appliedenergistics2:item.PaintBall.Red",
        version="1.7.10",
    )
    assert fluix == "Fluix ME Covered Cable"
    assert white == "White ME Smart Cable"
    assert paint == "Red Paint Ball"


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath("../MinecraftVersions/1.7.10/mods").is_dir(),
    reason="1.7.10 mods not available",
)
def test_item_catalog_resolves_ae2_block_display_names() -> None:
    load_item_catalog.cache_clear()
    fluix = resolve_catalog_display_name(
        "appliedenergistics2:tile.BlockFluix",
        None,
        version="1.7.10",
    )
    sky_stone = resolve_catalog_display_name(
        "appliedenergistics2:tile.BlockSkyStone",
        0,
        version="1.7.10",
    )
    sky_stone_block = resolve_catalog_display_name(
        "appliedenergistics2:tile.BlockSkyStone",
        1,
        version="1.7.10",
    )
    assert fluix == "Fluix Block"
    assert sky_stone == "Sky Stone"
    assert sky_stone_block == "Sky Stone Block"


def _write_test_ore_dict(version_root: Path) -> None:
    (version_root / "ore_dict.json").write_text(
        """
        {
          "crystalCertusQuartz": {
            "item": "appliedenergistics2:item.ItemMultiMaterial",
            "metadata": 0
          },
          "stickWood": "minecraft:stick",
          "itemSilicon": {
            "item": "appliedenergistics2:item.ItemMultiMaterial",
            "metadata": 5
          }
        }
        """,
        encoding="utf-8",
    )


def test_ae2_recipe_inputs_keep_distinct_metadata(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    version_root = isolated_minecraft_versions / version
    _write_test_ore_dict(version_root)
    recipe_root = isolated_minecraft_versions / version / "recipe" / "ae2-recipes"
    recipe_root.mkdir(parents=True, exist_ok=True)
    (recipe_root / "oredict.recipe").write_text(
        "ore=ae2:ItemMaterial.CertusQuartzCrystal -> crystalCertusQuartz\n",
        encoding="utf-8",
    )
    (recipe_root / "tools.certus-quartz.recipe").write_text(
        """
        shaped=
            oredictionary:crystalCertusQuartz oredictionary:crystalCertusQuartz,
            oredictionary:crystalCertusQuartz oredictionary:stickWood,
            _ oredictionary:stickWood
            -> ae2:ToolCertusQuartzAxe
        """,
        encoding="utf-8",
    )

    load_item_catalog.cache_clear()
    result = load_ae2_recipe_directory(recipe_root, version=version)
    assert len(result.recipes) == 1
    recipe = result.recipes[0]
    metas = {part.metadata for part in recipe.inputs}
    assert 0 in metas

    summary = to_recipe_summary(recipe, version=version)
    assert any("certus" in item.name.lower() for item in summary.inputs)
    assert any(item.name.lower() == "stick" for item in summary.inputs)


def test_ingredient_registry_registers_metadata_specific_names(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    _write_test_ore_dict(isolated_minecraft_versions / version)
    recipe_manager._clear_caches()
    registry = get_version_ingredient_registry(version)
    certus = registry.register(
        "appliedenergistics2:item.ItemMultiMaterial",
        metadata=0,
        version=version,
    )
    silicon = registry.register(
        "appliedenergistics2:item.ItemMultiMaterial",
        metadata=5,
        version=version,
    )
    assert certus.display_name != silicon.display_name
