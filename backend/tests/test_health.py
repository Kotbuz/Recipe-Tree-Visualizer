from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "recipe-tree-visualizer"}


def test_list_mods_empty() -> None:
    response = client.get("/mods")

    assert response.status_code == 200
    assert response.json() == {"mods": []}


def test_search_items_empty() -> None:
    response = client.get("/items/search", params={"q": "stick"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "stick"
    assert body["items"] == []


def test_calculate_production_not_implemented() -> None:
    response = client.post(
        "/graph/calculate",
        json={
            "target_item_id": "minecraft:stick",
            "target_rate_per_minute": 100,
            "graph": {"item_nodes": [], "recipe_nodes": [], "edges": []},
        },
    )

    assert response.status_code == 501
