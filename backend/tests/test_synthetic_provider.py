from app.recipes.manager import recipe_manager
from app.recipes.providers.synthetic import SyntheticProvider
from app.recipes.types import RecipeType
from app.services.recipe_service import _resolve_vanilla_jar_path, recipe_service
import pytest


def _require_vanilla_jar(version: str = "26.2") -> None:
    if _resolve_vanilla_jar_path(version) is None:
        pytest.skip(f"No vanilla jar found for version {version}")


def test_synthetic_provider_builds_brewing_recipes() -> None:
    result = SyntheticProvider().load("26.2")

    brewing = [recipe for recipe in result.recipes if recipe.recipe_type == RecipeType.BREWING]
    assert len(brewing) >= 20

    awkward = next(recipe for recipe in brewing if recipe.id.endswith("/awkward"))
    assert {part.item_id for part in awkward.inputs} == {
        "minecraft:glass_bottle",
        "minecraft:nether_wart",
    }
    assert awkward.outputs[0].item_id == "minecraft:potion_awkward"
    assert awkward.catalyst_id == "minecraft:brewing_stand"


def test_synthetic_provider_builds_compost_recipes() -> None:
    result = SyntheticProvider().load("26.2")

    compost = [recipe for recipe in result.recipes if recipe.recipe_type == RecipeType.COMPOSTING]
    assert len(compost) >= 40

    wheat = next(
        recipe for recipe in compost if recipe.id == "minecraft:synthetic/compost/minecraft/wheat_seeds"
    )
    assert wheat.outputs[0].item_id == "minecraft:bone_meal"
    assert wheat.outputs[0].chance == 0.3


def test_synthetic_provider_builds_anvil_repair_from_jar_tags() -> None:
    _require_vanilla_jar()
    result = SyntheticProvider().load("26.2")

    repairs = [recipe for recipe in result.recipes if recipe.recipe_type == RecipeType.ANVIL_REPAIR]
    assert repairs

    iron_pickaxe = next(
        recipe
        for recipe in repairs
        if recipe.id == "minecraft:synthetic/anvil/repair/minecraft/iron_pickaxe"
    )
    assert {part.item_id for part in iron_pickaxe.inputs} == {
        "minecraft:iron_pickaxe",
        "minecraft:iron_ingot",
    }
    assert iron_pickaxe.outputs[0].item_id == "minecraft:iron_pickaxe"


def test_recipe_manager_merges_synthetic_recipes() -> None:
    _require_vanilla_jar()
    with_synthetic = recipe_manager.get_version_recipes("26.2", include_synthetic=True)
    without_synthetic = recipe_manager.get_version_recipes("26.2", include_synthetic=False)

    assert len(with_synthetic) > len(without_synthetic)
    assert any(recipe.recipe_type == RecipeType.BREWING for recipe in with_synthetic)
    assert all(recipe.recipe_type != RecipeType.BREWING for recipe in without_synthetic)


def test_focus_finds_brewing_recipe() -> None:
    _require_vanilla_jar()
    results = recipe_service.search_recipes(
        version="26.2",
        focus_item="minecraft:potion_healing",
        focus_role="output",
        limit=10,
    )

    assert results
    assert any(recipe.machine_type == "minecraft:brewing" for recipe in results)
