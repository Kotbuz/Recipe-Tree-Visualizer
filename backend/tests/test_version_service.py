from pathlib import Path

import pytest

from app.services.version_service import item_name_to_texture_id, version_service


def test_item_name_to_texture_id() -> None:
    assert item_name_to_texture_id("Oak Planks") == "oak_planks"


def test_resolve_jar_path_prefers_version_client_jar() -> None:
    jar_path = version_service.resolve_jar_path("26.2")
    if jar_path is None:
        pytest.skip("26.2 is not installed in MinecraftVersions")
    assert jar_path.name in {"client.jar", "26.2.jar"}


def test_list_versions_includes_jar_version() -> None:
    versions = version_service.list_versions()
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2.jar is not present in MinecraftVersions")
    assert "26.2" in versions


def test_renderer_jar_path_for_installed_version() -> None:
    if version_service.resolve_jar_path("26.2") is None:
        pytest.skip("26.2 is not installed in MinecraftVersions")
    renderer_path = version_service.renderer_jar_path("26.2")
    assert renderer_path is not None
    assert Path(renderer_path).is_file()
    assert Path(renderer_path).name in {"client.jar", "26.2.jar"}


def test_renderer_jar_path_maps_to_renderer_root_in_docker(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions_root = tmp_path / "app-versions"
    renderer_root = tmp_path / "data-minecraft"
    version_dir = versions_root / "1.21.1"
    version_dir.mkdir(parents=True)
    renderer_root.mkdir(parents=True)
    jar_path = version_dir / "client.jar"
    jar_path.write_bytes(b"x" * 2048)

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(versions_root))
    monkeypatch.setenv("RENDERER_MINECRAFT_ROOT", str(renderer_root))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
    service = version_service_module.get_version_service()

    mapped = service.renderer_jar_path("1.21.1")
    assert mapped == str(renderer_root / "1.21.1" / "client.jar")

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()


def test_resolve_item_icon_prefers_rendered_icons(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    version_dir = tmp_path / "9.9"
    rendered_dir = version_dir / "profiles" / "default" / "rendered-icons"
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


def test_list_item_icons_skips_phantom_names_when_rendered_exists(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version_dir = tmp_path / "9.9"
    rendered_dir = version_dir / "profiles" / "default" / "rendered-icons"
    rendered_dir.mkdir(parents=True)
    (rendered_dir / "oak_planks.png").write_bytes(b"rendered")

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
    service = version_service_module.get_version_service()

    icons = service.list_item_icons("9.9")
    assert icons == ["oak_planks.png"]
    assert "iron_block.png" not in icons

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()


def test_resolve_item_icon_skips_jar_when_rendered_dir_exists(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version_dir = tmp_path / "9.9"
    rendered_dir = version_dir / "profiles" / "default" / "rendered-icons"
    rendered_dir.mkdir(parents=True)
    (rendered_dir / "stone.png").write_bytes(b"rendered")

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
    service = version_service_module.get_version_service()

    assert service.resolve_item_icon("9.9", "oak_planks.png") is None

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()


def test_list_item_icons_skips_phantom_names_when_rendered_dir_empty(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version_dir = tmp_path / "9.9"
    rendered_dir = version_dir / "profiles" / "default" / "rendered-icons"
    rendered_dir.mkdir(parents=True)

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
    service = version_service_module.get_version_service()

    assert service.list_item_icons("9.9") == []

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()
