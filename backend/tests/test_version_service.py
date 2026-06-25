import pytest

from app.services.version_service import item_name_to_texture_id, version_service


def test_item_name_to_texture_id() -> None:
    assert item_name_to_texture_id("Oak Planks") == "oak_planks"


def test_resolve_jar_path_flat_layout() -> None:
    jar_path = version_service.resolve_jar_path("26.2")
    if jar_path is None:
        pytest.skip("26.2.jar is not present in MinecraftVersions")
    assert jar_path.name == "26.2.jar"


def test_list_versions_includes_jar_version() -> None:
    versions = version_service.list_versions()
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present in MinecraftVersions")
    assert "26.2" in versions


def test_renderer_jar_path_for_flat_jar() -> None:
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present in MinecraftVersions")
    assert version_service.renderer_jar_path("26.2") == "/data/minecraft/26.2.jar"


def test_resolve_item_icon_prefers_rendered_icons(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    version_dir = tmp_path / "9.9"
    rendered_dir = version_dir / "rendered-icons"
    legacy_dir = version_dir / "item-textures"
    rendered_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)
    (rendered_dir / "stone.png").write_bytes(b"rendered")
    (legacy_dir / "stone.png").write_bytes(b"legacy")

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
    service = version_service_module.get_version_service()

    resolved = service.resolve_item_icon_path("9.9", "stone.png")
    assert resolved is not None
    assert resolved.read_bytes() == b"rendered"

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
