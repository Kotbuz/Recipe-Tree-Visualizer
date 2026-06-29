from __future__ import annotations

from pathlib import Path

import pytest
from app.recipes.manager import recipe_manager
from app.recipes.models import Recipe, RecipeIO
from app.recipes.providers.kubejs_script_parser import (
    apply_kubejs_removes,
    normalize_kubejs_item_id,
    parse_kubejs_output,
    parse_kubejs_server_script,
    parse_kubejs_server_scripts,
)
from app.recipes.providers.kubejs_scripts import KubejsScriptProvider
from app.recipes.types import RecipeType
from app.services.profile_service import profile_service
from app.services.version_service import version_service

CRAFTING_SNIPPET = """
ServerEvents.recipes(event => {
    event.remove({ id: 'stellaris:misc/water_separator' })
    event.shaped('framedblocks:framed_cube', ["SPS", "P P", "SPS"], { S: 'stick', P: '#planks' }).id('framedblocks:framed_cube')
    event.shapeless('immersiveengineering:dust_saltpeter', ['1x techopolis:silver_dust', '1x techopolis:nickel_dust']).id('techopolis:dust_saltpeter')
})
"""

CUSTOM_SNIPPET = """
ServerEvents.recipes(event => {
    event.custom({
        "type": "ae2:inscriber",
        "ingredients": {
            "middle": { "item": "actuallyadditions:canola_seeds" }
        },
        "mode": "inscribe",
        "result": { "id": "actuallyadditions:crystallized_canola_seed" }
    }).id('techopolis:ae2/crystallized_canola_seed_inscriber')
})
"""


def test_parse_remove_shaped_shapeless() -> None:
    parsed = parse_kubejs_server_script(CRAFTING_SNIPPET, source_file="crafting.js")
    assert len(parsed.removes) == 1
    assert parsed.removes[0].recipe_id == "stellaris:misc/water_separator"
    assert len(parsed.recipe_payloads) == 2

    shaped = parsed.recipe_payloads[0]
    assert shaped["type"] == "minecraft:crafting_shaped"
    assert shaped["__recipe_id"] == "framedblocks:framed_cube"
    assert shaped["result"] == {"id": "framedblocks:framed_cube", "count": 1}

    shapeless = parsed.recipe_payloads[1]
    assert shapeless["type"] == "minecraft:crafting_shapeless"
    assert shapeless["__recipe_id"] == "techopolis:dust_saltpeter"


def test_parse_custom_recipe() -> None:
    parsed = parse_kubejs_server_script(CUSTOM_SNIPPET, source_file="mods/AE2.js")
    assert len(parsed.recipe_payloads) == 1
    payload = parsed.recipe_payloads[0]
    assert payload["type"] == "ae2:inscriber"
    assert payload["__recipe_id"] == "techopolis:ae2/crystallized_canola_seed_inscriber"


def test_normalize_kubejs_item_id() -> None:
    assert normalize_kubejs_item_id("oak_planks") == "minecraft:oak_planks"
    assert normalize_kubejs_item_id("#planks") == "tag:planks"
    assert normalize_kubejs_item_id("6x techopolis:silver_dust") == "techopolis:silver_dust"


def test_parse_kubejs_output() -> None:
    assert parse_kubejs_output("'16x mekanism:basic_mechanical_pipe'") == (
        "mekanism:basic_mechanical_pipe",
        16,
    )


def test_apply_kubejs_removes_by_id_and_output() -> None:
    recipes = {
        "stellaris:misc/water_separator": Recipe(
            id="stellaris:misc/water_separator",
            recipe_type=RecipeType.CRAFTING_SHAPED,
            category_id="crafting",
            catalyst_id="minecraft:crafting_table",
            inputs=[],
            outputs=[RecipeIO(item_id="stellaris:water_separator", amount=1.0)],
            duration_ticks=None,
            source="mod",
            mod_id="stellaris",
        ),
        "techopolis:grout": Recipe(
            id="techopolis:grout",
            recipe_type=RecipeType.CRAFTING_SHAPELESS,
            category_id="crafting",
            catalyst_id="minecraft:crafting_table",
            inputs=[],
            outputs=[RecipeIO(item_id="techopolis:grout", amount=3.0)],
            duration_ticks=None,
            source="kubejs",
            mod_id="techopolis",
        ),
    }

    parsed = parse_kubejs_server_script(CRAFTING_SNIPPET, source_file="crafting.js")
    removed = apply_kubejs_removes(recipes, parsed.removes)
    assert "stellaris:misc/water_separator" in removed
    assert "stellaris:misc/water_separator" not in recipes
    assert "techopolis:grout" in recipes


def test_kubejs_script_provider_builds_recipes(isolated_minecraft_versions: Path) -> None:
    version = "1.7.10"
    profile = profile_service.create_profile(version, "KubeJS Scripts", activate=False)
    scripts_dir = version_service.kubejs_dir(version, profile.profile_id) / "server_scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "crafting.js").write_text(CRAFTING_SNIPPET, encoding="utf-8")
    (scripts_dir / "mods").mkdir()
    (scripts_dir / "mods" / "AE2.js").write_text(CUSTOM_SNIPPET, encoding="utf-8")

    recipe_manager._clear_caches()
    result = KubejsScriptProvider().load(version, profile.profile_id)

    assert len(result.removes) == 1
    shaped = next(recipe for recipe in result.recipes if recipe.id == "framedblocks:framed_cube")
    assert shaped.recipe_type == RecipeType.CRAFTING_SHAPED
    assert shaped.outputs[0].item_id == "framedblocks:framed_cube"
    assert any(skip.recipe_id.startswith("techopolis:ae2") for skip in result.skipped) or any(
        recipe.id == "techopolis:ae2/crystallized_canola_seed_inscriber"
        for recipe in result.recipes
    )


@pytest.mark.skipif(
    not Path("P:/Practice/Recipe-Tree-Visualizer/LocalFiles/kubejs/server_scripts").is_dir(),
    reason="LocalFiles kubejs not available",
)
def test_parse_local_techopolis_scripts() -> None:
    scripts_dir = Path("P:/Practice/Recipe-Tree-Visualizer/LocalFiles/kubejs/server_scripts")
    parsed = parse_kubejs_server_scripts(scripts_dir)
    assert len(parsed.removes) > 10
    assert len(parsed.recipe_payloads) > 100
