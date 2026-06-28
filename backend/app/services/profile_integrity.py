from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.services.kubejs_import import (
    KubejsImportStats,
    copy_kubejs_from_directory,
    copy_kubejs_from_zip_members,
    detect_kubejs_root,
    list_importable_kubejs_relative_paths,
    should_import_kubejs_relative_path,
)
from app.services.profile_storage import read_profile_meta
from app.services.version_service import version_service


@dataclass(frozen=True)
class IntegrityIssue:
    category: str
    status: str
    profile_count: int
    source_count: int
    missing_count: int
    message: str


@dataclass(frozen=True)
class IntegrityReport:
    profile_id: str
    source: str
    source_path: str | None
    source_available: bool
    healthy: bool
    can_sync: bool
    issues: tuple[IntegrityIssue, ...]


@dataclass(frozen=True)
class ProfileSyncStats:
    jars_synced: int = 0
    config_files_synced: int = 0
    script_files_synced: int = 0
    kubejs_server_scripts_synced: int = 0
    kubejs_data_files_synced: int = 0
    kubejs_asset_files_synced: int = 0


class ProfileSyncSourceUnavailableError(Exception):
    pass


def check_profile_integrity(version: str, profile_id: str, *, mc_version: str) -> IntegrityReport:
    profile_dir = version_service.profile_dir(version, profile_id)
    meta = read_profile_meta(profile_dir)
    source = str(meta.get("source", "default"))
    source_path_raw = meta.get("source_path")
    source_archive_raw = meta.get("source_archive")

    source_path = (
        Path(str(source_path_raw)).expanduser().resolve()
        if isinstance(source_path_raw, str) and source_path_raw.strip()
        else None
    )
    source_archive = (
        Path(str(source_archive_raw)).expanduser().resolve()
        if isinstance(source_archive_raw, str) and source_archive_raw.strip()
        else None
    )

    issues: list[IntegrityIssue] = []
    source_available = False

    if source == "instance_path" and source_path is not None and source_path.is_dir():
        source_available = True
        roots = _detect_content_roots(source_path, mc_version=mc_version, is_zip=False)
        issues.extend(_compare_directory_sources(profile_dir, source_path, roots))
        issues.extend(_compare_kubejs_directory(profile_dir, source_path))
    elif source == "modpack_zip" and source_archive is not None and source_archive.is_file():
        source_available = True
        with zipfile.ZipFile(source_archive) as archive:
            names = archive.namelist()
            roots = _detect_content_roots(names, mc_version=mc_version, is_zip=True)
            issues.extend(_compare_zip_sources(profile_dir, archive, names, roots))
            issues.extend(_compare_kubejs_zip(profile_dir, archive, names))
    else:
        issues.append(
            IntegrityIssue(
                category="source",
                status="unavailable",
                profile_count=0,
                source_count=0,
                missing_count=0,
                message=_source_unavailable_message(source, source_path, source_archive),
            )
        )

    healthy = all(issue.status == "ok" for issue in issues)
    can_sync = source_available and any(issue.missing_count > 0 for issue in issues)
    return IntegrityReport(
        profile_id=profile_id,
        source=source,
        source_path=str(source_path) if source_path is not None else None,
        source_available=source_available,
        healthy=healthy,
        can_sync=can_sync,
        issues=tuple(issues),
    )


def sync_profile_from_source(
    version: str,
    profile_id: str,
    *,
    mc_version: str,
) -> ProfileSyncStats:
    report = check_profile_integrity(version, profile_id, mc_version=mc_version)
    if not report.source_available:
        raise ProfileSyncSourceUnavailableError(report.issues[0].message if report.issues else "Источник недоступен")
    if not report.can_sync:
        return ProfileSyncStats()

    profile_dir = version_service.profile_dir(version, profile_id)
    meta = read_profile_meta(profile_dir)
    source = str(meta.get("source", "default"))
    source_path = Path(str(meta["source_path"])).expanduser().resolve()
    source_archive = (
        Path(str(meta["source_archive"])).expanduser().resolve()
        if isinstance(meta.get("source_archive"), str)
        else None
    )

    if source == "instance_path":
        roots = _detect_content_roots(source_path, mc_version=mc_version, is_zip=False)
        stats = _sync_from_directory(profile_dir, source_path, roots)
        kubejs_stats = _sync_kubejs_directory(profile_dir, source_path)
        return _merge_sync_stats(stats, kubejs_stats)

    if source == "modpack_zip" and source_archive is not None:
        with zipfile.ZipFile(source_archive) as archive:
            names = archive.namelist()
            roots = _detect_content_roots(names, mc_version=mc_version, is_zip=True)
            stats = _sync_from_zip(profile_dir, archive, names, roots)
            kubejs_stats = _sync_kubejs_zip(profile_dir, archive, names)
            return _merge_sync_stats(stats, kubejs_stats)

    raise ProfileSyncSourceUnavailableError("Источник синхронизации недоступен")


def _source_unavailable_message(
    source: str,
    source_path: Path | None,
    source_archive: Path | None,
) -> str:
    if source == "instance_path":
        if source_path is None:
            return "Путь к инстансу не сохранён — повторите импорт из папки Prism."
        return f"Папка инстанса не найдена: {source_path}"
    if source == "modpack_zip":
        if source_archive is None:
            return "Путь к архиву модпака не сохранён — повторите импорт .zip."
        return f"Архив модпака не найден: {source_archive}"
    if source == "default":
        return "Профиль default не привязан к модпаку — проверка не требуется."
    return "Для этого профиля нет сохранённого источника — повторите импорт модпака."


def _compare_directory_sources(
    profile_dir: Path,
    source_root: Path,
    roots: dict[str, str],
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []

    mods_prefix = roots.get("mods")
    if mods_prefix:
        source_names = _jar_names_under(source_root / mods_prefix)
        profile_names = _jar_names_under(profile_dir / "mods")
        issues.append(_issue_for_sets("mods", "моды (.jar)", profile_names, source_names))

    for category, label in (("config", "config"), ("scripts", "scripts")):
        prefix = roots.get(category)
        if not prefix:
            continue
        source_files = _relative_files_under(source_root / prefix)
        profile_files = _relative_files_under(profile_dir / category)
        issues.append(_issue_for_sets(category, label, profile_files, source_files))

    return issues


def _compare_zip_sources(
    profile_dir: Path,
    archive: zipfile.ZipFile,
    names: list[str],
    roots: dict[str, str],
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []

    mods_prefix = roots.get("mods")
    if mods_prefix:
        source_names = _jar_names_in_zip(names, mods_prefix)
        profile_names = _jar_names_under(profile_dir / "mods")
        issues.append(_issue_for_sets("mods", "моды (.jar)", profile_names, source_names))

    for category, label in (("config", "config"), ("scripts", "scripts")):
        prefix = roots.get(category)
        if not prefix:
            continue
        source_files = _relative_files_in_zip(names, prefix)
        profile_files = _relative_files_under(profile_dir / category)
        issues.append(_issue_for_sets(category, label, profile_files, source_files))

    return issues


def _compare_kubejs_directory(profile_dir: Path, source_root: Path) -> list[IntegrityIssue]:
    kubejs_prefix = detect_kubejs_root(source_root, is_zip=False)
    if not kubejs_prefix:
        return [
            IntegrityIssue(
                category="kubejs",
                status="ok",
                profile_count=0,
                source_count=0,
                missing_count=0,
                message="KubeJS в источнике не найден",
            )
        ]

    source_paths = list_importable_kubejs_relative_paths(source_root / kubejs_prefix)
    profile_paths = list_importable_kubejs_relative_paths(profile_dir / "kubejs")
    return [
        _issue_for_posix_sets(
            "kubejs",
            "KubeJS (скрипты и data)",
            profile_paths,
            source_paths,
        )
    ]


def _compare_kubejs_zip(profile_dir: Path, archive: zipfile.ZipFile, names: list[str]) -> list[IntegrityIssue]:
    kubejs_prefix = detect_kubejs_root(names, is_zip=True)
    if not kubejs_prefix:
        return [
            IntegrityIssue(
                category="kubejs",
                status="ok",
                profile_count=0,
                source_count=0,
                missing_count=0,
                message="KubeJS в архиве не найден",
            )
        ]

    source_paths = _importable_kubejs_paths_in_zip(names, kubejs_prefix)
    profile_paths = list_importable_kubejs_relative_paths(profile_dir / "kubejs")
    return [
        _issue_for_posix_sets(
            "kubejs",
            "KubeJS (скрипты и data)",
            profile_paths,
            source_paths,
        )
    ]


def _issue_for_sets(
    category: str,
    label: str,
    profile_items: set[str],
    source_items: set[str],
) -> IntegrityIssue:
    missing = source_items - profile_items
    if not source_items:
        return IntegrityIssue(
            category=category,
            status="ok",
            profile_count=len(profile_items),
            source_count=0,
            missing_count=0,
            message=f"{label}: в источнике нет файлов",
        )
    if not missing:
        return IntegrityIssue(
            category=category,
            status="ok",
            profile_count=len(profile_items),
            source_count=len(source_items),
            missing_count=0,
            message=f"{label}: всё на месте ({len(profile_items)} файлов)",
        )
    return IntegrityIssue(
        category=category,
        status="missing",
        profile_count=len(profile_items),
        source_count=len(source_items),
        missing_count=len(missing),
        message=f"{label}: не хватает {len(missing)} из {len(source_items)} файлов",
    )


def _issue_for_posix_sets(
    category: str,
    label: str,
    profile_items: frozenset[PurePosixPath],
    source_items: frozenset[PurePosixPath],
) -> IntegrityIssue:
    missing = set(source_items) - set(profile_items)
    if not source_items:
        return IntegrityIssue(
            category=category,
            status="ok",
            profile_count=len(profile_items),
            source_count=0,
            missing_count=0,
            message=f"{label}: в источнике нет импортируемых файлов",
        )
    if not missing:
        return IntegrityIssue(
            category=category,
            status="ok",
            profile_count=len(profile_items),
            source_count=len(source_items),
            missing_count=0,
            message=f"{label}: всё на месте ({len(profile_items)} файлов)",
        )
    return IntegrityIssue(
        category=category,
        status="missing",
        profile_count=len(profile_items),
        source_count=len(source_items),
        missing_count=len(missing),
        message=f"{label}: не хватает {len(missing)} из {len(source_items)} файлов",
    )


def _sync_from_directory(
    profile_dir: Path,
    source_root: Path,
    roots: dict[str, str],
) -> ProfileSyncStats:
    stats = ProfileSyncStats()

    mods_prefix = roots.get("mods")
    if mods_prefix:
        stats = ProfileSyncStats(
            jars_synced=_sync_missing_jars(source_root / mods_prefix, profile_dir / "mods"),
        )

    for category in ("config", "scripts"):
        prefix = roots.get(category)
        if not prefix:
            continue
        copied = _sync_missing_tree(source_root / prefix, profile_dir / category)
        if category == "config":
            stats = ProfileSyncStats(
                jars_synced=stats.jars_synced,
                config_files_synced=copied,
                script_files_synced=stats.script_files_synced,
            )
        else:
            stats = ProfileSyncStats(
                jars_synced=stats.jars_synced,
                config_files_synced=stats.config_files_synced,
                script_files_synced=copied,
            )

    return stats


def _sync_from_zip(
    profile_dir: Path,
    archive: zipfile.ZipFile,
    names: list[str],
    roots: dict[str, str],
) -> ProfileSyncStats:
    stats = ProfileSyncStats()

    mods_prefix = roots.get("mods")
    if mods_prefix:
        profile_mods = profile_dir / "mods"
        profile_mods.mkdir(parents=True, exist_ok=True)
        existing = _jar_names_under(profile_mods)
        jars_synced = 0
        prefix_path = PurePosixPath(mods_prefix)
        for member in names:
            if not member.lower().endswith(".jar"):
                continue
            pure = PurePosixPath(member)
            try:
                relative = pure.relative_to(prefix_path)
            except ValueError:
                continue
            jar_name = relative.name
            if jar_name in existing:
                continue
            destination = profile_mods / jar_name
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            jars_synced += 1
        stats = ProfileSyncStats(jars_synced=jars_synced)

    for category in ("config", "scripts"):
        prefix = roots.get(category)
        if not prefix:
            continue
        copied = _sync_missing_zip_tree(archive, names, prefix, profile_dir / category)
        if category == "config":
            stats = ProfileSyncStats(
                jars_synced=stats.jars_synced,
                config_files_synced=copied,
                script_files_synced=stats.script_files_synced,
            )
        else:
            stats = ProfileSyncStats(
                jars_synced=stats.jars_synced,
                config_files_synced=stats.config_files_synced,
                script_files_synced=copied,
            )

    return stats


def _sync_kubejs_directory(profile_dir: Path, source_root: Path) -> KubejsImportStats:
    kubejs_prefix = detect_kubejs_root(source_root, is_zip=False)
    if not kubejs_prefix:
        return KubejsImportStats()

    source_kubejs = source_root / kubejs_prefix
    destination_kubejs = profile_dir / "kubejs"
    source_paths = list_importable_kubejs_relative_paths(source_kubejs)
    profile_paths = list_importable_kubejs_relative_paths(destination_kubejs)
    missing = set(source_paths) - set(profile_paths)
    if not missing:
        return KubejsImportStats()

    stats = KubejsImportStats()
    for relative in sorted(missing):
        source_file = source_kubejs / Path(*relative.parts)
        if not source_file.is_file():
            continue
        category = should_import_kubejs_relative_path(relative)
        if category is None:
            continue
        target = destination_kubejs / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
        stats = _increment_kubejs_stats(stats, category)
    return stats


def _sync_kubejs_zip(profile_dir: Path, archive: zipfile.ZipFile, names: list[str]) -> KubejsImportStats:
    kubejs_prefix = detect_kubejs_root(names, is_zip=True)
    if not kubejs_prefix:
        return KubejsImportStats()

    destination_kubejs = profile_dir / "kubejs"
    source_paths = _importable_kubejs_paths_in_zip(names, kubejs_prefix)
    profile_paths = list_importable_kubejs_relative_paths(destination_kubejs)
    missing = set(source_paths) - set(profile_paths)
    if not missing:
        return KubejsImportStats()

    stats = KubejsImportStats()
    prefix_path = PurePosixPath(kubejs_prefix)
    for relative in sorted(missing):
        member = str(prefix_path / relative).replace("\\", "/")
        if member not in names:
            continue
        category = should_import_kubejs_relative_path(relative)
        if category is None:
            continue
        target = destination_kubejs / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        stats = _increment_kubejs_stats(stats, category)
    return stats


def _merge_sync_stats(stats: ProfileSyncStats, kubejs_stats: KubejsImportStats) -> ProfileSyncStats:
    return ProfileSyncStats(
        jars_synced=stats.jars_synced,
        config_files_synced=stats.config_files_synced,
        script_files_synced=stats.script_files_synced,
        kubejs_server_scripts_synced=kubejs_stats.server_script_files,
        kubejs_data_files_synced=kubejs_stats.data_files,
        kubejs_asset_files_synced=kubejs_stats.asset_files,
    )


def _sync_missing_jars(source_mods: Path, profile_mods: Path) -> int:
    if not source_mods.is_dir():
        return 0
    profile_mods.mkdir(parents=True, exist_ok=True)
    existing = _jar_names_under(profile_mods)
    synced = 0
    for jar_path in sorted(source_mods.rglob("*.jar")):
        if not jar_path.is_file() or jar_path.name in existing:
            continue
        shutil.copy2(jar_path, profile_mods / jar_path.name)
        synced += 1
    return synced


def _sync_missing_tree(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    synced = 0
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(source)
        target = destination / relative
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        synced += 1
    return synced


def _sync_missing_zip_tree(
    archive: zipfile.ZipFile,
    names: list[str],
    prefix: str,
    destination: Path,
) -> int:
    prefix_path = PurePosixPath(prefix)
    synced = 0
    for member in names:
        if member.endswith("/"):
            continue
        pure = PurePosixPath(member)
        try:
            relative = pure.relative_to(prefix_path)
        except ValueError:
            continue
        target = destination / Path(*relative.parts)
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        synced += 1
    return synced


def _jar_names_under(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {path.name for path in root.glob("*.jar") if path.is_file()}


def _jar_names_in_zip(names: list[str], prefix: str) -> set[str]:
    prefix_path = PurePosixPath(prefix)
    jars: set[str] = set()
    for member in names:
        if not member.lower().endswith(".jar"):
            continue
        pure = PurePosixPath(member)
        try:
            relative = pure.relative_to(prefix_path)
        except ValueError:
            continue
        jars.add(relative.name)
    return jars


def _relative_files_under(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {"/".join(path.relative_to(root).parts) for path in root.rglob("*") if path.is_file()}


def _relative_files_in_zip(names: list[str], prefix: str) -> set[str]:
    prefix_path = PurePosixPath(prefix)
    files: set[str] = set()
    for member in names:
        if member.endswith("/"):
            continue
        pure = PurePosixPath(member)
        try:
            relative = pure.relative_to(prefix_path)
        except ValueError:
            continue
        files.add("/".join(relative.parts))
    return files


def _importable_kubejs_paths_in_zip(names: list[str], kubejs_prefix: str) -> frozenset[PurePosixPath]:
    prefix_path = PurePosixPath(kubejs_prefix)
    paths: set[PurePosixPath] = set()
    for member in names:
        if member.endswith("/"):
            continue
        pure = PurePosixPath(member)
        try:
            relative = pure.relative_to(prefix_path)
        except ValueError:
            continue
        if should_import_kubejs_relative_path(relative) is not None:
            paths.add(relative)
    return frozenset(paths)


def _increment_kubejs_stats(stats: KubejsImportStats, category: str) -> KubejsImportStats:
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


def _detect_content_roots(
    source: Path | list[str],
    *,
    mc_version: str,
    is_zip: bool,
) -> dict[str, str]:
    roots: dict[str, str] = {}
    candidates = [
        (
            "mods",
            ("mods", "minecraft/mods", "overrides/mods", f"overrides/mods/{mc_version}"),
        ),
        ("config", ("config", "minecraft/config", "overrides/config")),
        ("scripts", ("scripts", "minecraft/scripts", "overrides/scripts")),
    ]
    for category, options in candidates:
        matched: list[str] = []
        for option in options:
            if is_zip:
                if any(
                    name == option or name.startswith(f"{option}/")
                    for name in source  # type: ignore[union-attr]
                ):
                    matched.append(option)
            elif (source / option).exists():  # type: ignore[operator]
                matched.append(option)
        if not matched:
            continue
        if category == "mods":
            roots[category] = max(
                matched,
                key=lambda path: (
                    _count_jars_under_prefix(source, path, is_zip=is_zip),
                    -path.count("/"),
                ),
            )
        else:
            roots[category] = max(
                matched,
                key=lambda path: (
                    _count_files_under_prefix(source, path, is_zip=is_zip),
                    -path.count("/"),
                ),
            )

    if not is_zip and "mods" not in roots:
        source_path = source  # type: ignore[assignment]
        for option in (
            "minecraft/mods",
            "mods",
            "overrides/mods",
            f"overrides/mods/{mc_version}",
        ):
            if _count_jars_under_prefix(source_path, option, is_zip=False) > 0:
                roots["mods"] = option
                break
    return roots


def _count_jars_under_prefix(
    source: Path | list[str],
    prefix: str,
    *,
    is_zip: bool,
) -> int:
    if is_zip:
        names = source  # type: ignore[assignment]
        return sum(
            1
            for name in names
            if (name == prefix or name.startswith(f"{prefix}/"))
            and name.lower().endswith(".jar")
        )
    root = source / prefix  # type: ignore[operator]
    if not root.is_dir():
        return 0
    return sum(1 for path in root.rglob("*.jar") if path.is_file())


def _count_files_under_prefix(
    source: Path | list[str],
    prefix: str,
    *,
    is_zip: bool,
) -> int:
    if is_zip:
        names = source  # type: ignore[assignment]
        return sum(
            1
            for name in names
            if (name == prefix or name.startswith(f"{prefix}/"))
            and not name.endswith("/")
        )
    root = source / prefix  # type: ignore[operator]
    if not root.is_dir():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())
