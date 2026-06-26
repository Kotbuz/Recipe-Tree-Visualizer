from app.recipes.adapters import to_recipe_summary
from app.recipes.legacy_item_icons import (
    resolve_legacy_display_name,
    resolve_legacy_icon_id,
)
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType
from app.services.jvm_export_status_service import analyze_recipe_export_status


def test_legacy_dye_metadata_maps_to_lapis() -> None:
    assert resolve_legacy_icon_id("minecraft:dye", 4, version="1.7.10") == "lapis_lazuli"
    assert resolve_legacy_display_name("minecraft:dye", 4, version="1.7.10") == "lapis lazuli"


def test_legacy_fire_maps_to_iron_for_display() -> None:
    assert resolve_legacy_icon_id("minecraft:fire", None, version="1.7.10") == "iron_ingot"


def test_recipe_summary_uses_legacy_icon_for_metadata() -> None:
    recipe = Recipe(
        id="minecraft:export/crafting/0",
        recipe_type=RecipeType.CRAFTING_SHAPED,
        category_id="crafting",
        catalyst_id=None,
        inputs=[RecipeIO(item_id="minecraft:dye", amount=9.0, metadata=4)],
        outputs=[RecipeIO(item_id="minecraft:lapis_block", amount=1.0)],
        duration_ticks=None,
        source="vanilla",
        mod_id="minecraft",
        raw_type="crafting_shaped",
    )
    summary = to_recipe_summary(recipe, version="1.7.10")
    assert summary.inputs[0].icon_id == "lapis_lazuli"
    assert summary.inputs[0].name == "lapis lazuli"


def test_export_status_detects_missing_ae2_dependencies(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    mods_dir = isolated_minecraft_versions / version / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "appliedenergistics2-rv3-beta-6.jar").write_bytes(b"fake")
    (isolated_minecraft_versions / version / "recipe" / "minecraft__export__crafting__0.json").write_text(
        '{"id":"minecraft:export/crafting/0"}',
        encoding="utf-8",
    )

    status = analyze_recipe_export_status(version)
    assert status.missing_dependencies
    assert status.missing_dependencies[0].mod_id == "appliedenergistics2"
    assert "CodeChickenLib" in status.missing_dependencies[0].missing_dependencies
    assert any("appliedenergistics2" in warning for warning in status.warnings)
