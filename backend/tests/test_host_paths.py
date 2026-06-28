from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

import pytest

from app.services.host_paths import (
    format_stored_path_for_display,
    map_windows_path_to_container,
    resolve_host_filesystem_path,
)


def test_windows_path_resolves_on_native_windows() -> None:
    if os.name != "nt":
        pytest.skip("Windows-only test")

    resolved = resolve_host_filesystem_path(
        r"C:\Users\efimi\AppData\Roaming\PrismLauncher\instances\Techopolis 3"
    )
    assert resolved.is_absolute()
    assert resolved.drive.upper() == "C:"
    assert "efimi" in resolved.parts


def test_windows_path_mapping_env() -> None:
    instances = Path(os.environ.get("TEMP", ".")) / "prism-instances-test"
    instance = instances / "Techopolis 3"
    instance.mkdir(parents=True, exist_ok=True)

    windows_prefix = r"C:\Users\efimi\AppData\Roaming\PrismLauncher\instances"
    previous = os.environ.get("HOST_PATH_MAPPINGS")
    os.environ["HOST_PATH_MAPPINGS"] = f"{windows_prefix}={instances}"
    try:
        resolved = resolve_host_filesystem_path(f"{windows_prefix}\\Techopolis 3")
        assert resolved == instance
    finally:
        if previous is None:
            os.environ.pop("HOST_PATH_MAPPINGS", None)
        else:
            os.environ["HOST_PATH_MAPPINGS"] = previous


def test_format_stored_path_for_display() -> None:
    assert (
        format_stored_path_for_display(
            r"C:\Users\efimi\AppData\Roaming\PrismLauncher\instances\Techopolis 3"
        )
        == r"C:\Users\efimi\AppData\Roaming\PrismLauncher\instances\Techopolis 3"
    )


def test_instances_host_path_builds_mapping(tmp_path: Path) -> None:
    instances = tmp_path / "launcher-instances"
    instance = instances / "Techopolis 3"
    instance.mkdir(parents=True)

    previous_mappings = os.environ.get("HOST_PATH_MAPPINGS")
    previous_host = os.environ.get("INSTANCES_HOST_PATH")
    previous_container = os.environ.get("INSTANCES_CONTAINER_PATH")
    os.environ.pop("HOST_PATH_MAPPINGS", None)
    os.environ["INSTANCES_HOST_PATH"] = r"C:/Users/efimi/launcher/instances"
    os.environ["INSTANCES_CONTAINER_PATH"] = str(instances)
    try:
        resolved = resolve_host_filesystem_path(r"C:\Users\efimi\launcher\instances\Techopolis 3")
        assert resolved == instance
    finally:
        if previous_mappings is None:
            os.environ.pop("HOST_PATH_MAPPINGS", None)
        else:
            os.environ["HOST_PATH_MAPPINGS"] = previous_mappings
        if previous_host is None:
            os.environ.pop("INSTANCES_HOST_PATH", None)
        else:
            os.environ["INSTANCES_HOST_PATH"] = previous_host
        if previous_container is None:
            os.environ.pop("INSTANCES_CONTAINER_PATH", None)
        else:
            os.environ["INSTANCES_CONTAINER_PATH"] = previous_container


def test_map_windows_path_to_container_relative_parts(tmp_path: Path) -> None:
    host_root = tmp_path / "host"
    os.environ["HOST_PATH_MAPPINGS"] = rf"C:\prism={host_root}"
    try:
        mapped = map_windows_path_to_container(PureWindowsPath(r"C:\prism\Techopolis 3"))
        assert mapped == host_root / "Techopolis 3"
    finally:
        os.environ.pop("HOST_PATH_MAPPINGS", None)
