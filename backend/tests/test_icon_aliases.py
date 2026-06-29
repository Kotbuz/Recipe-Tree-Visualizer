import pytest
from app.services.version_service import item_name_to_texture_id, version_service


def test_item_name_to_texture_id_resolves_tags() -> None:
    assert item_name_to_texture_id("planks") == "oak_planks"
    assert item_name_to_texture_id("stone tool materials") == "cobblestone"


def test_read_jar_texture_for_logs_tag() -> None:
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present")

    payload = version_service.read_jar_texture_bytes("26.2", "oak_log.png")
    assert payload is not None
    assert len(payload) > 0
