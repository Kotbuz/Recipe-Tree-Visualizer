from __future__ import annotations

from pathlib import Path

from app.services.profile_storage import (
    read_profile_forge_version,
    resolve_profile_forge_build,
    write_profile_meta,
)


def test_resolve_profile_forge_build_backfills_from_crash_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile_dir = tmp_path / "profiles" / "ftb"
    profile_dir.mkdir(parents=True)
    write_profile_meta(
        profile_dir,
        profile_id="ftb",
        name="FTB",
        source="modpack_zip",
    )

    crash_dir = tmp_path / "recipe-exporter" / "forge-runtime" / "1.7.10" / "crash-reports"
    crash_dir.mkdir(parents=True)
    (crash_dir / "crash-2026-06-26_server.txt").write_text(
        "Missing Mods:\n\tForge : [10.13.4.1558,)\n",
        encoding="utf-8",
    )

    class FakeSettings:
        minecraft_versions_path = tmp_path / "MinecraftVersions"

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: FakeSettings(),
    )

    forge_build = resolve_profile_forge_build(profile_dir, minecraft_version="1.7.10")
    assert forge_build == "10.13.4.1558"
    assert read_profile_forge_version(profile_dir) == "10.13.4.1558"
