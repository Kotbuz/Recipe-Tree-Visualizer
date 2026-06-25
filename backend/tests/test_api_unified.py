from pathlib import Path

from app.main import app
from app.recipes.focus import RecipeIngredientRole
from app.recipes.manager import recipe_manager
from app.services.mod_service import mod_service
from app.services.recipe_service import _resolve_vanilla_jar_path, recipe_service
from fastapi.testclient import TestClient
import pytest

client = TestClient(app)

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"


def _require_recipe_source(version: str = "26.2") -> None:
    if recipe_service.get_recipes(version):
        return
    pytest.skip(f"No recipe source found for Minecraft version {version}")


def test_search_recipes_focus_item_output() -> None:
    _require_recipe_source()
    response = client.get(
        "/recipes",
        params={
            "version": "26.2",
            "focus_item": "minecraft:oak_planks",
            "focus_role": RecipeIngredientRole.OUTPUT.value,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    recipes = response.json()["recipes"]
    assert recipes
    assert all(
        any(item.get("item_id", "").endswith("oak_planks") for item in recipe["outputs"])
        for recipe in recipes
    )


def test_search_recipes_focus_tag_planks_output() -> None:
    _require_recipe_source()
    response = client.get(
        "/recipes",
        params={
            "version": "26.2",
            "focus_item": "tag:minecraft:planks",
            "focus_role": RecipeIngredientRole.OUTPUT.value,
            "limit": 50,
        },
    )

    assert response.status_code == 200
    recipes = response.json()["recipes"]
    assert recipes
    assert any(
        item.get("item_id", "").endswith("_planks")
        for recipe in recipes
        for item in recipe["outputs"]
    )


def test_search_recipes_focus_item_includes_item_id() -> None:
    _require_recipe_source()
    response = client.get(
        "/recipes",
        params={
            "version": "26.2",
            "q": "stick",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    recipes = response.json()["recipes"]
    assert recipes
    assert recipes[0]["outputs"][0]["item_id"]


def test_items_search_returns_version_ingredients() -> None:
    _require_recipe_source()
    response = client.get("/items/search", params={"q": "stick", "version": "26.2", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "stick"
    assert body["items"]


def test_items_recipes_via_recipe_manager(isolated_minecraft_versions) -> None:
    mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)], "26.2")

    response = client.get(
        "/items/naturescompass:naturescompass/recipes",
        params={"version": "26.2", "include_mods": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "naturescompass:naturescompass"
    assert body["recipes"]
    assert any(recipe["recipe_id"] == "naturescompass:natures_compass" for recipe in body["recipes"])


def test_recipe_service_focus_role() -> None:
    _require_recipe_source()
    results = recipe_service.search_recipes(
        version="26.2",
        focus_item="minecraft:oak_planks",
        focus_role="output",
        limit=10,
    )
    assert results
    assert results[0].outputs[0].item_id
