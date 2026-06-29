import os
import zipfile
from pathlib import Path

os.environ.setdefault("MODS_AUTO_LOAD_ON_STARTUP", "false")

import pytest
from app.core.config import get_settings
from app.indexer.mod_registry import registry
from app.recipes.manager import recipe_manager
from app.services.mod_service import mod_service
from app.services.version_service import version_service


def _write_minimal_client_jar(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("assets/minecraft/textures/item/stick.png", b"png" * 512)
        archive.writestr(
            "data/minecraft/recipe/stick.json",
            (
                b'{"type":"minecraft:crafting_shaped","pattern":["A","A"],'
                b'"key":{"A":{"item":"minecraft:oak_planks"}},'
                b'"result":{"item":"minecraft:stick","count":4}}'
            ),
        )
        archive.writestr("padding.txt", b"0" * 2048)


@pytest.fixture
def isolated_minecraft_versions(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "minecraft-versions"
    root.mkdir()
    monkeypatch.setenv("MINECRAFT_VERSIONS_DIR", str(root))
    get_settings.cache_clear()

    for version in ("26.2", "1.18.2", "1.21.11", "1.12.2", "1.7.10"):
        version_service.ensure_version_layout(version)
        _write_minimal_client_jar(version_service.client_jar_path(version))

    yield root


@pytest.fixture(autouse=True)
def clear_mod_registry() -> None:
    registry.clear()
    recipe_manager.clear_mods()
    mod_service.clear_loaded_state()
    yield
    registry.clear()
    recipe_manager.clear_mods()
    mod_service.clear_loaded_state()
