import httpx
import pytest

from app.core.config import get_settings
from app.services.jvm_recipe_export_service import JvmRecipeExportService


def test_http_exporter_uses_recipe_exporter_url(
    monkeypatch: pytest.MonkeyPatch,
    isolated_minecraft_versions,
) -> None:
    version = "1.7.10"
    recipe_dir = isolated_minecraft_versions / version / "recipe"
    recipe_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("RECIPE_EXPORTER_URL", "http://recipe-exporter:8090")
    monkeypatch.setenv("RECIPE_EXPORTER_MODE", "docker")
    get_settings.cache_clear()

    (recipe_dir / "minecraft__export__crafting__0.json").write_text(
        '{"id": "minecraft:export/crafting/0"}',
        encoding="utf-8",
    )

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"status": "ok", "exported": 1, "duration_seconds": 12.5}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url: str, json: dict[str, object]):
            assert url == "http://recipe-exporter:8090/export"
            assert json == {"version": version, "force": False}
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    service = JvmRecipeExportService()
    exported = service._run_http_exporter(version, recipe_dir)

    assert exported == 1
