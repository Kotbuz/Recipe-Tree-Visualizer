import pytest
from app.indexer.mod_registry import registry
from app.recipes.manager import recipe_manager


@pytest.fixture(autouse=True)
def clear_mod_registry() -> None:
    registry._mods.clear()
    recipe_manager.clear_mods()
    yield
    registry._mods.clear()
    recipe_manager.clear_mods()
