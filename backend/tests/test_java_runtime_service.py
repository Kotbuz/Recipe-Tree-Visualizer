from __future__ import annotations

from pathlib import Path

import pytest

from app.services import java_runtime_service


def test_java_home_from_executable_windows_style(tmp_path: Path) -> None:
    home = tmp_path / "jdk-21"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    java_exe = bin_dir / "java.exe"
    java_exe.write_text("", encoding="utf-8")

    resolved = java_runtime_service.java_home_from_executable(java_exe)
    assert resolved == home.resolve()


def test_detect_java_major_from_release(tmp_path: Path) -> None:
    home = tmp_path / "jdk-21"
    home.mkdir()
    (home / "release").write_text('JAVA_VERSION="21.0.1"\n', encoding="utf-8")

    assert java_runtime_service.detect_java_major(home) == 21


def test_settings_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(java_runtime_service, "_SETTINGS_FILE", tmp_path / "java_settings.json")

    home = tmp_path / "jdk-21"
    (home / "bin").mkdir(parents=True)
    (home / "bin" / "java.exe").write_text("", encoding="utf-8")
    (home / "release").write_text('JAVA_VERSION="21.0.1"\n', encoding="utf-8")

    runtime = java_runtime_service.set_java_home(21, str(home))
    assert runtime.major == 21
    assert java_runtime_service.get_configured_java_homes()[21] == str(home.resolve())

    java_runtime_service.clear_java_home(21)
    assert 21 not in java_runtime_service._read_settings_homes()
