from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "recipe-tree-visualizer"}


def test_list_mods_empty(isolated_minecraft_versions) -> None:
    response = client.get("/mods", params={"version": "26.2"})

    assert response.status_code == 200
    assert response.json() == {"mods": []}


def test_search_items_no_matches() -> None:
    response = client.get(
        "/items/search",
        params={"q": "zzznonexistentitem999", "version": "26.2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "zzznonexistentitem999"
    assert body["items"] == []


def test_calculate_production_rejects_empty_graph() -> None:
    response = client.post(
        "/graph/calculate",
        json={
            "target_item_id": "minecraft:stick",
            "target_rate_per_minute": 100,
            "graph": {"item_nodes": [], "recipe_nodes": [], "edges": []},
        },
    )

    assert response.status_code == 400
    assert "No recipe in graph produces" in response.json()["detail"]
