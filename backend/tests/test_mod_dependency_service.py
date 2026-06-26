import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.mod_deps.catalog import catalog_entry_for, load_dependency_catalog
from app.mod_deps.curseforge import ResolvedModFile, _pick_file
from app.mod_deps.resolver import DependencyResolution
from app.services.mod_dependency_service import (
    ModDependencyService,
    _collect_missing_dependencies,
)


def test_load_dependency_catalog_1710() -> None:
    catalog = load_dependency_catalog("1.7.10")
    assert "CodeChickenLib" in catalog
    assert catalog["CodeChickenLib"].curseforge_project_id == 222979


def test_catalog_entry_for_unknown_uses_name() -> None:
    catalog = load_dependency_catalog("1.7.10")
    entry = catalog_entry_for(catalog, "SomeUnknownMod")
    assert entry.dependency_name == "SomeUnknownMod"
    assert entry.search_terms == ("SomeUnknownMod",)


def test_pick_curseforge_file_prefers_release() -> None:
    files = [
        {
            "id": 1,
            "fileName": "alpha.jar",
            "gameVersions": ["1.7.10"],
            "releaseType": 3,
            "fileDate": "2014-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "fileName": "CodeChickenLib-1.7.10-1.1.3.141-universal.jar",
            "gameVersions": ["1.7.10"],
            "releaseType": 1,
            "fileDate": "2014-06-01T00:00:00Z",
        },
    ]
    picked = _pick_file(files, "1.7.10", ("1.7.10", "universal"))
    assert picked is not None
    assert picked["id"] == 2


def test_collect_missing_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = "1.7.10"
    version_dir = tmp_path / version
    version_dir.mkdir(parents=True)
    (version_dir / "client.jar").write_bytes(b"jar" * 512)
    mods_dir = version_dir / "profiles" / "default" / "mods"
    recipe_dir = version_dir / "profiles" / "default" / "recipe"
    mods_dir.mkdir(parents=True)
    recipe_dir.mkdir(parents=True)
    (mods_dir / "Thaumcraft-4.2.3.5.jar").write_bytes(b"j")
    (recipe_dir / "minecraft__test.json").write_text(
        json.dumps({"id": "minecraft:test"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    missing = _collect_missing_dependencies(version)
    assert "Baubles" in missing


def test_download_missing_dependencies_no_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = "1.7.10"
    version_dir = tmp_path / version
    version_dir.mkdir(parents=True)
    (version_dir / "client.jar").write_bytes(b"jar" * 512)
    (version_dir / "profiles" / "default" / "mods").mkdir(parents=True)
    (version_dir / "profiles" / "default" / "recipe").mkdir(parents=True)

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services import version_service as version_service_module

    get_settings.cache_clear()
    version_service_module.get_version_service.cache_clear()

    service = ModDependencyService()
    with patch(
        "app.services.mod_dependency_service._collect_missing_dependencies",
        return_value=(),
    ):
        with patch(
            "app.services.mod_dependency_service.version_service.list_installed_versions",
            return_value=[version],
        ):
            result = service.download_missing_dependencies(version)

    assert result.requested == ()
    assert result.all_resolved is True
    assert result.export_triggered is False


def test_download_one_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = "1.7.10"
    version_dir = tmp_path / version
    mods_dir = version_dir / "profiles" / "default" / "mods"
    mods_dir.mkdir(parents=True)

    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(tmp_path))
    monkeypatch.setenv("CURSEFORGE_API_KEY", "test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()

    service = ModDependencyService()
    resolver = MagicMock()
    resolved = ResolvedModFile(
        file_name="CodeChickenLib-1.7.10.jar",
        download_url="https://example.com/mod.jar",
        source="curseforge",
        project_url="https://example.com/project",
    )
    resolver.resolve.return_value = DependencyResolution(
        dependency_name="CodeChickenLib",
        resolved=resolved,
        manual_url="https://example.com/manual",
    )

    def fake_download(_url: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jar")

    with patch.object(service, "_download_file", side_effect=fake_download) as download_file:
        result = service._download_one(
            version=version,
            dependency_name="CodeChickenLib",
            resolver=resolver,
            mods_dir=mods_dir,
            cache_dir=tmp_path / "cache",
        )

    assert result.status == "downloaded"
    assert (mods_dir / "CodeChickenLib-1.7.10.jar").is_file()
    download_file.assert_called_once()
