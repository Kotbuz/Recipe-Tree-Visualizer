import pytest
from app.indexer.mod_registry import registry
from app.recipes.manager import recipe_manager


@pytest.fixture(autouse=True)
def clear_mod_registry() -> None:
    registry.clear()
    recipe_manager.clear_mods()
    yield
    registry.clear()
    recipe_manager.clear_mods()
