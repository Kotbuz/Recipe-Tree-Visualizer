from pathlib import Path

from app.recipes.adapters import to_recipe_summary
from app.recipes.legacy_item_icons import (
    resolve_legacy_display_name,
    resolve_legacy_icon_id,
)
from app.recipes.models import Recipe, RecipeIO
from app.recipes.types import RecipeType
from app.services.jvm_export_status_service import analyze_recipe_export_status
from app.services.version_service import version_service


def test_legacy_dye_metadata_maps_to_lapis() -> None:
    assert resolve_legacy_icon_id("minecraft:dye", 4, version="1.7.10") == "lapis_lazuli"
    assert resolve_legacy_display_name("minecraft:dye", 4, version="1.7.10") == "lapis lazuli"


def test_legacy_stone_slab_metadata_maps_to_quartz_slab() -> None:
    assert resolve_legacy_icon_id("minecraft:stone_slab", 7, version="1.7.10") == "quartz_slab"
    assert resolve_legacy_display_name("minecraft:stone_slab", 7, version="1.7.10") == "quartz slab"
    assert resolve_legacy_icon_id("minecraft:stone_slab", 4, version="1.7.10") == "brick_slab"


def test_legacy_quartz_block_metadata() -> None:
    assert resolve_legacy_icon_id("minecraft:quartz_block", 1, version="1.7.10") == "chiseled_quartz_block"
    assert resolve_legacy_display_name("minecraft:quartz_block", 0, version="1.7.10") == "quartz block"


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
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "appliedenergistics2-rv3-beta-6.jar").write_bytes(b"fake")
    (version_service.recipe_dir(version) / "minecraft__export__crafting__0.json").write_text(
        '{"id":"minecraft:export/crafting/0"}',
        encoding="utf-8",
    )

    status = analyze_recipe_export_status(version)
    assert status.missing_dependencies == ()
    assert not any("CodeChickenLib" in warning for warning in status.warnings)


def test_export_status_detects_forgemultipart_needs_codechickencore(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "ForgeMultipart-1.2.0.345-universal.jar").write_bytes(b"fake")
    (version_service.recipe_dir(version) / "minecraft__export__crafting__0.json").write_text(
        '{"id":"minecraft:export/crafting/0"}',
        encoding="utf-8",
    )

    status = analyze_recipe_export_status(version)
    assert status.missing_dependencies
    assert status.missing_dependencies[0].mod_id == "forgemultipart"
    assert status.missing_dependencies[0].missing_dependencies == ("CodeChickenCore",)


def test_export_status_shows_export_hint_when_recipe_dir_empty(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "appliedenergistics2-rv3-beta-6.jar").write_bytes(b"fake")
    (mods_dir / "CodeChickenCore-1.4.16.jar").write_bytes(b"fake")

    status = analyze_recipe_export_status(version)
    assert status.exported_recipe_count == 0
    assert status.missing_dependencies == ()
    assert "JVM-экспорт рецептов" in status.warnings[0]
    assert "codechickencore" not in status.mods_without_recipes


def test_export_status_warns_about_ic2_experimental_jar(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "industrialcraft-2-2.2.828-experimental.jar").write_bytes(b"fake")

    status = analyze_recipe_export_status(version)
    assert any("experimental" in warning.lower() for warning in status.warnings)


def test_export_status_warns_about_forgemultipart_jar(
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "ForgeMultipart-1.7.10-1.2.0.345-universal.jar").write_bytes(b"fake")

    status = analyze_recipe_export_status(version)
    assert any("forgemultipart" in warning.lower() for warning in status.warnings)


def test_extract_forge_loader_errors_detects_forgemultipart_nosuchfield(
    tmp_path: Path,
) -> None:
    from app.services.jvm_export_status_service import _extract_forge_loader_errors

    log_path = tmp_path / "latest.log"
    log_path.write_text(
        "Caused by: java.lang.NoSuchFieldError: field_150478_aa\n"
        "\tat codechicken.multipart.minecraft.Content.blockTypes(Content.java:40)\n",
        encoding="utf-8",
    )

    errors = _extract_forge_loader_errors(log_path)
    assert any("forgemultipart" in error.lower() for error in errors)


def test_export_status_skips_dependency_heuristics_for_non_jvm(
    isolated_minecraft_versions,
) -> None:
    version = "1.12.2"
    mods_dir = version_service.mods_dir(version)
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "appliedenergistics2-rv3-beta-6.jar").write_bytes(b"fake")

    status = analyze_recipe_export_status(version)
    assert status.layout == "assets"
    assert status.missing_dependencies == ()
    assert status.warnings == ()
