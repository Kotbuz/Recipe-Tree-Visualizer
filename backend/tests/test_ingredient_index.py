import pytest
from app.services.version_service import version_service


def test_ingredient_index_endpoint() -> None:
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present")

    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/versions/26.2/ingredient-index")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "26.2"
    assert "tag:minecraft:stone_crafting_materials" in body["tags"]
    assert "minecraft:cobblestone" in body["tags"]["tag:minecraft:stone_crafting_materials"]
    assert body["aliases"]["planks"] == "oak planks"
