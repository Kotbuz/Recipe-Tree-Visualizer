from __future__ import annotations

import errno
import json
import os
import re
import shutil
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PROFILE_ID = "default"
PROFILE_META_FILENAME = "profile.json"
ACTIVE_PROFILE_FILENAME = "_active.json"

_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def profile_storage_key(version: str, profile_id: str) -> str:
    return f"{version}::{profile_id}"


def normalize_profile_id(raw: str) -> str:
    candidate = raw.strip().lower().replace(" ", "-")
    candidate = re.sub(r"[^a-z0-9_-]+", "-", candidate)
    candidate = candidate.strip("-_")
    if not candidate:
        candidate = "profile"
    return candidate[:64]


def slug_profile_id(name: str) -> str:
    base = normalize_profile_id(name)
    suffix = uuid.uuid4().hex[:8]
    trimmed = base[: max(1, 64 - 9)]
    return f"{trimmed}-{suffix}"


def validate_profile_id(profile_id: str) -> str:
    normalized = profile_id.strip()
    if not _PROFILE_ID_RE.match(normalized):
        raise ValueError(
            "profile_id может содержать только строчные латинские буквы, цифры, «-» и «_»"
        )
    return normalized


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_profile_meta(profile_dir: Path) -> dict[str, object]:
    meta_path = profile_dir / PROFILE_META_FILENAME
    if not meta_path.is_file():
        return {
            "profile_id": profile_dir.name,
            "name": profile_dir.name,
            "source": "default",
            "created_at": utc_now_iso(),
        }
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid profile metadata: {meta_path}")
    return payload


def write_profile_meta(
    profile_dir: Path,
    *,
    profile_id: str,
    name: str,
    source: str,
    created_at: str | None = None,
    loader: str | None = None,
    forge_version: str | None = None,
    source_path: str | None = None,
    source_archive: str | None = None,
) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "profile_id": profile_id,
        "name": name,
        "source": source,
        "created_at": created_at or utc_now_iso(),
    }
    if loader:
        payload["loader"] = loader
    if forge_version:
        payload["forge_version"] = forge_version
    if source_path:
        payload["source_path"] = source_path
    if source_archive:
        payload["source_archive"] = source_archive
    (profile_dir / PROFILE_META_FILENAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def update_profile_forge_version(profile_dir: Path, forge_version: str) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    meta = read_profile_meta(profile_dir)
    meta["forge_version"] = forge_version.strip()
    (profile_dir / PROFILE_META_FILENAME).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_profile_forge_version(profile_dir: Path) -> str | None:
    meta = read_profile_meta(profile_dir)
    value = meta.get("forge_version")
    return value if isinstance(value, str) and value.strip() else None


def resolve_profile_forge_build(
    profile_dir: Path,
    *,
    minecraft_version: str,
) -> str | None:
    """Возвращает Forge build для профиля, при необходимости определяет и сохраняет."""
    existing = read_profile_forge_version(profile_dir)
    if existing:
        return existing

    from app.services.modpack_version_detector import (
        detect_forge_from_library_paths,
        detect_modpack_version_from_directory,
        detect_modpack_version_from_zip,
        infer_forge_build_from_crash_reports,
    )

    meta = read_profile_meta(profile_dir)
    source_path = meta.get("source_path")
    if isinstance(source_path, str) and source_path.strip():
        detected = detect_modpack_version_from_directory(Path(source_path))
        if detected is not None and detected.forge_version:
            update_profile_forge_version(profile_dir, detected.forge_version)
            return detected.forge_version

    source_archive = meta.get("source_archive")
    if isinstance(source_archive, str) and source_archive.strip():
        archive_path = Path(source_archive)
        if archive_path.is_file():
            detected = detect_modpack_version_from_zip(archive_path)
            if detected is not None and detected.forge_version:
                update_profile_forge_version(profile_dir, detected.forge_version)
                return detected.forge_version
            try:
                import zipfile

                with zipfile.ZipFile(archive_path) as archive:
                    forge_build = detect_forge_from_library_paths(archive.namelist())
            except zipfile.BadZipFile:
                forge_build = None
            if forge_build:
                update_profile_forge_version(profile_dir, forge_build)
                return forge_build

    inferred = infer_forge_build_from_crash_reports(minecraft_version)
    if inferred:
        update_profile_forge_version(profile_dir, inferred)
        return inferred
    return None


def read_active_profile_id(profiles_dir: Path) -> str | None:
    active_path = profiles_dir / ACTIVE_PROFILE_FILENAME
    if not active_path.is_file():
        return None
    payload = json.loads(active_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        profile_id = payload.get("profile_id")
        if isinstance(profile_id, str) and profile_id:
            return profile_id
    return None


def write_active_profile_id(profiles_dir: Path, profile_id: str) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    payload = {"profile_id": profile_id}
    (profiles_dir / ACTIVE_PROFILE_FILENAME).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_profile_subdirs(profile_dir: Path) -> None:
    for name in ("mods", "recipe", "config", "scripts", "kubejs", "rendered-icons"):
        (profile_dir / name).mkdir(parents=True, exist_ok=True)


def count_mod_jars(mods_dir: Path) -> int:
    if not mods_dir.is_dir():
        return 0
    return sum(1 for path in mods_dir.rglob("*.jar") if path.is_file())


def has_profile_meta(profile_dir: Path) -> bool:
    return (profile_dir / PROFILE_META_FILENAME).is_file()


def _rmtree_onerror(func, path: str, exc_info) -> None:
    """Снимает read-only на Windows и повторяет удаление."""
    exc = exc_info[1]
    if not isinstance(exc, OSError):
        raise exc
    if exc.errno not in (errno.EACCES, errno.EPERM, errno.EBUSY):
        raise exc
    os.chmod(path, stat.S_IWUSR | stat.S_IREAD)
    func(path)


def remove_profile_dir(profile_dir: Path) -> None:
    if not profile_dir.exists():
        return
    shutil.rmtree(profile_dir, onerror=_rmtree_onerror)


def prune_orphan_profile_dirs(profiles_dir: Path) -> list[str]:
    """Удаляет папки без profile.json и без jar-модов (остатки кэша recipe/)."""
    removed: list[str] = []
    if not profiles_dir.is_dir():
        return removed

    for entry in profiles_dir.iterdir():
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        if entry.name == DEFAULT_PROFILE_ID:
            continue
        if has_profile_meta(entry):
            continue
        if count_mod_jars(entry / "mods") > 0:
            write_profile_meta(
                entry,
                profile_id=entry.name,
                name=entry.name,
                source="recovered",
            )
            continue
        remove_profile_dir(entry)
        removed.append(entry.name)
    return removed


def migrate_legacy_version_layout(version_dir: Path) -> bool:
    """Переносит version/{mods,recipe,config,scripts} в profiles/default/."""
    profiles_dir = version_dir / "profiles"
    default_profile = profiles_dir / DEFAULT_PROFILE_ID
    legacy_mods = version_dir / "mods"

    if profiles_dir.exists() and default_profile.exists():
        return False
    if not legacy_mods.is_dir() and not (version_dir / "recipe").is_dir():
        return False

    profiles_dir.mkdir(parents=True, exist_ok=True)
    default_profile.mkdir(parents=True, exist_ok=True)
    ensure_profile_subdirs(default_profile)

    moved = False
    for subdir in ("mods", "recipe", "config", "scripts"):
        source = version_dir / subdir
        if not source.exists():
            continue
        destination = default_profile / subdir
        if destination.exists() and any(destination.iterdir()):
            continue
        if destination.exists():
            destination.rmdir()
        shutil.move(str(source), str(destination))
        moved = True

    if not (default_profile / PROFILE_META_FILENAME).is_file():
        write_profile_meta(
            default_profile,
            profile_id=DEFAULT_PROFILE_ID,
            name="По умолчанию",
            source="default",
        )

    if read_active_profile_id(profiles_dir) is None:
        write_active_profile_id(profiles_dir, DEFAULT_PROFILE_ID)

    return moved
