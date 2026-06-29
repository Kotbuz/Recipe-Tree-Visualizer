from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

KUBEJS_ROOT_CANDIDATES = (
    "kubejs",
    "minecraft/kubejs",
    "overrides/kubejs",
)


@dataclass(frozen=True)
class KubejsImportStats:
    server_script_files: int = 0
    data_files: int = 0
    asset_files: int = 0

    @property
    def total_files(self) -> int:
        return self.server_script_files + self.data_files + self.asset_files


def detect_kubejs_root(
    source: Path | list[str],
    *,
    is_zip: bool,
) -> str | None:
    matched: list[str] = []
    for option in KUBEJS_ROOT_CANDIDATES:
        if is_zip:
            names = source  # type: ignore[assignment]
            if any(
                name == option or name.startswith(f"{option}/")
                for name in names
            ):
                matched.append(option)
        elif (source / option).exists():  # type: ignore[operator]
            matched.append(option)
    if not matched:
        return None
    return max(matched, key=lambda path: (-path.count("/"), path))


def should_import_kubejs_relative_path(relative: PurePosixPath) -> str | None:
    """Return import category (server_scripts, data, assets) or None to skip."""
    if not relative.parts:
        return None

    if relative.parts[0] == "server_scripts":
        return "server_scripts"

    if relative.parts[0] == "data" and _is_recipe_or_machine_data_path(relative):
        return "data"

    if relative.parts[0] == "assets" and _is_machine_asset_path(relative):
        return "assets"

    return None


def list_importable_kubejs_relative_paths(kubejs_dir: Path) -> frozenset[PurePosixPath]:
    if not kubejs_dir.is_dir():
        return frozenset()

    paths: set[PurePosixPath] = set()
    for file_path in kubejs_dir.rglob("*"):
        if not file_path.is_file():
            continue
        relative = PurePosixPath(*file_path.relative_to(kubejs_dir).parts)
        if should_import_kubejs_relative_path(relative) is not None:
            paths.add(relative)
    return frozenset(paths)


def copy_kubejs_from_directory(source_kubejs: Path, destination_kubejs: Path) -> KubejsImportStats:
    stats = KubejsImportStats()
    if not source_kubejs.is_dir():
        return stats

    for file_path in sorted(source_kubejs.rglob("*")):
        if not file_path.is_file():
            continue
        relative = PurePosixPath(*file_path.relative_to(source_kubejs).parts)
        category = should_import_kubejs_relative_path(relative)
        if category is None:
            continue

        target = destination_kubejs / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        stats = _increment_stats(stats, category)

    return stats


def copy_kubejs_from_zip_members(
    archive: zipfile.ZipFile,
    member_names: list[str],
    kubejs_prefix: str,
    destination_kubejs: Path,
) -> KubejsImportStats:
    stats = KubejsImportStats()
    prefix_path = PurePosixPath(kubejs_prefix)

    for member in member_names:
        if member.endswith("/"):
            continue
        pure = PurePosixPath(member)
        try:
            relative = pure.relative_to(prefix_path)
        except ValueError:
            continue

        category = should_import_kubejs_relative_path(relative)
        if category is None:
            continue

        target = destination_kubejs / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        stats = _increment_stats(stats, category)

    return stats


def _is_recipe_or_machine_data_path(relative: PurePosixPath) -> bool:
    parts = relative.parts
    return "recipe" in parts or "machine" in parts


def _is_machine_asset_path(relative: PurePosixPath) -> bool:
    parts = relative.parts
    if len(parts) < 4 or parts[0] != "assets":
        return False
    if parts[2] == "models" and parts[3] == "machine":
        return True
    if parts[2] == "textures" and parts[3] in {"block", "gui"}:
        return True
    return False


def _increment_stats(stats: KubejsImportStats, category: str) -> KubejsImportStats:
    if category == "server_scripts":
        return KubejsImportStats(
            stats.server_script_files + 1,
            stats.data_files,
            stats.asset_files,
        )
    if category == "data":
        return KubejsImportStats(
            stats.server_script_files,
            stats.data_files + 1,
            stats.asset_files,
        )
    if category == "assets":
        return KubejsImportStats(
            stats.server_script_files,
            stats.data_files,
            stats.asset_files + 1,
        )
    return stats
