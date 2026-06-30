"""Тесты для фазы 1: счётчик предметов снимка, имена файлов блок-текстур, реестр рендера."""

from __future__ import annotations

from app.services.block_texture_service import (
    _output_filename,
    _texture_ref_to_jar_entry,
)
from app.services.recipe_snapshot_service import (
    count_snapshot_items,
    read_snapshot_status,
)


def test_count_snapshot_items_unique_across_sections() -> None:
    payload = {
        "recipes": {
            "mod:a": {
                "inputs": [{"item": "minecraft:iron_ingot"}, "minecraft:stick"],
                "outputs": [{"item_id": "mod:gear"}],
            },
            "mod:b": {
                "ingredients": [{"item": "minecraft:iron_ingot"}],
                "results": [{"id": "mod:plate"}],
            },
        }
    }
    # iron_ingot повторяется → считается один раз; всего 4 уникальных.
    assert count_snapshot_items(payload) == 4


def test_count_snapshot_items_handles_empty_or_malformed() -> None:
    assert count_snapshot_items({}) == 0
    assert count_snapshot_items({"recipes": []}) == 0
    assert count_snapshot_items({"recipes": {"x": "not-a-dict"}}) == 0


def test_texture_ref_to_jar_entry_namespaces() -> None:
    assert _texture_ref_to_jar_entry("minecraft:block/stone") == (
        "minecraft",
        "assets/minecraft/textures/block/stone.png",
    )
    # без namespace → minecraft по умолчанию
    assert _texture_ref_to_jar_entry("block/dirt") == (
        "minecraft",
        "assets/minecraft/textures/block/dirt.png",
    )
    # ссылки-переменные (#…) и пустые игнорируются
    assert _texture_ref_to_jar_entry("#all") is None
    assert _texture_ref_to_jar_entry("") is None


def test_output_filename_flattens_and_prefixes_mod_namespace() -> None:
    assert _output_filename("minecraft:block/stone") == "stone.png"
    assert _output_filename("minecraft:block/coral/tube") == "coral_tube.png"
    assert _output_filename("create:block/cogwheel") == "create_cogwheel.png"


def test_snapshot_status_reads_item_count(tmp_path, monkeypatch) -> None:
    from app.services import version_service as version_service_module
    from app.services.recipe_snapshot_service import commit_snapshot

    version = "1.21.1"
    profile_id = "phase1"
    (tmp_path / version / "profiles" / profile_id).mkdir(parents=True)
    monkeypatch.setattr(
        version_service_module.version_service,
        "profile_dir",
        lambda v, pid: tmp_path / v / "profiles" / pid,
    )

    commit_snapshot(
        version,
        profile_id,
        snapshot_payload={"recipes": {"x": {"inputs": [{"item": "minecraft:stick"}]}}},
        meta={
            "format_version": 1,
            "minecraft_version": version,
            "exported_at": "2026-01-01T00:00:00+00:00",
            "recipe_count": 1,
            "item_count": 7,
        },
    )
    status = read_snapshot_status(version, profile_id)
    assert status.item_count == 7


def test_asset_render_rejects_concurrent_start(monkeypatch) -> None:
    import threading

    from app.services.asset_render_service import AssetRenderService

    service = AssetRenderService()
    release = threading.Event()

    def fake_run(self, version, profile_id, full_rescan):  # noqa: ANN001
        state = self.get_state(version, profile_id)
        release.wait(timeout=5)
        state.icons.running = False
        state.blocks.running = False

    monkeypatch.setattr(AssetRenderService, "_run", fake_run)

    assert service.start("1.21.1", "p") is True
    # пока первый проход «идёт» — повторный запуск отклоняется
    assert service.start("1.21.1", "p") is False
    release.set()
