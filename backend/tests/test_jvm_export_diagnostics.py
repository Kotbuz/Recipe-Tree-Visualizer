from __future__ import annotations

from app.services.jvm_export_status_service import (
    _extract_forge_loader_errors,
    _extract_missing_mods_from_diagnostic,
    _jar_provides_dependency,
)


def test_jar_provides_dependency_codechickenlib_satisfies_core() -> None:
    assert _jar_provides_dependency(
        "CodeChickenLib-1.7.10-1.1.3.138-universal.jar",
        "CodeChickenCore",
    )


def test_jar_provides_dependency_buildcraft_core_from_unified_jar() -> None:
    assert _jar_provides_dependency("buildcraft-7.1.16.jar", "BuildCraft|Core")
    assert _jar_provides_dependency("buildcraft-compat-7.1.5.jar", "BuildCraft|Core")


def test_extract_missing_mods_from_crash_report() -> None:
    text = """
Missing Mods:
	IC2 : any

cpw.mods.fml.common.MissingModsException
"""
    assert _extract_missing_mods_from_diagnostic(text) == ["IC2"]


def test_extract_forge_loader_errors_reports_forge_version_mismatch(tmp_path) -> None:
    text = """
Missing Mods:
	Forge : [10.13.4.1558,)

Minecraft Forge 10.13.4.1448 177 mods loaded
cpw.mods.fml.common.MissingModsException
"""
    log_path = tmp_path / "latest.log"
    log_path.write_text(text, encoding="utf-8")
    messages = _extract_forge_loader_errors(log_path)
    assert any(
        "Forge 10.13.4.1558" in message and "10.13.4.1448" in message for message in messages
    )
    assert not any("отсутствует мод «Forge»" in message for message in messages)


def test_extract_forge_loader_errors_prioritizes_missing_mods(tmp_path) -> None:
    text = """
Missing Mods:
	IC2 : any

This crash report has been saved to: P:\\path\\crash.txt
"""
    log_path = tmp_path / "latest.log"
    log_path.write_text(text, encoding="utf-8")
    messages = _extract_forge_loader_errors(log_path)
    assert any("отсутствует мод «IC2»" in message for message in messages)
