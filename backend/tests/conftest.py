import pytest
from app.indexer.mod_registry import registry


@pytest.fixture(autouse=True)
def clear_mod_registry() -> None:
    registry._mods.clear()
    yield
    registry._mods.clear()
