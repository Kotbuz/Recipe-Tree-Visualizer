from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from loguru import logger

from app.schemas.profiles import ProfileSource, ProfileSummary
from app.services.profile_storage import (
    DEFAULT_PROFILE_ID,
    count_mod_jars,
    ensure_profile_subdirs,
    migrate_legacy_version_layout,
    normalize_profile_id,
    prune_orphan_profile_dirs,
    read_active_profile_id,
    read_profile_meta,
    remove_profile_dir,
    slug_profile_id,
    utc_now_iso,
    validate_profile_id,
    write_active_profile_id,
    write_profile_meta,
)
from app.services.version_service import version_service
from app.services.kubejs_import import (
    KubejsImportStats,
    copy_kubejs_from_directory,
    copy_kubejs_from_zip_members,
    detect_kubejs_root,
)
from app.services.host_paths import resolve_host_filesystem_path
from app.services.profile_integrity import (
    IntegrityReport,
    ProfileSyncSourceUnavailableError,
    ProfileSyncStats,
    check_profile_integrity,
    sync_profile_from_source,
)
from app.services.modpack_version_detector import (
    detect_modpack_version_from_directory,
    detect_modpack_version_from_zip,
)


class ProfileNotFoundError(Exception):
    def __init__(self, version: str, profile_id: str) -> None:
        super().__init__(f"Profile not found: {version}/{profile_id}")
        self.version = version
        self.profile_id = profile_id


class ProfileAlreadyExistsError(Exception):
    def __init__(self, profile_id: str) -> None:
        super().__init__(f"Profile already exists: {profile_id}")
        self.profile_id = profile_id


class InvalidModpackError(Exception):
    pass


class InvalidInstancePathError(Exception):
    pass


class ModpackVersionMismatchError(Exception):
    def __init__(
        self,
        requested_version: str,
        detected_version: str,
        modpack_name: str | None = None,
    ) -> None:
        self.requested_version = requested_version
        self.detected_version = detected_version
        self.modpack_name = modpack_name
        label = f"«{modpack_name}»" if modpack_name else "Модпак"
        super().__init__(
            f"{label} предназначен для Minecraft {detected_version}, "
            f"а не для {requested_version}"
        )


@dataclass(frozen=True)
class ModpackImportStats:
    jars_imported: int
    config_files_imported: int
    script_files_imported: int
    kubejs_server_scripts_imported: int = 0
    kubejs_data_files_imported: int = 0
    kubejs_asset_files_imported: int = 0


class ProfileService:
    def list_profiles(self, version: str) -> tuple[str, list[ProfileSummary]]:
        version_service.ensure_profiles_layout(version)
        profiles_dir = version_service.profiles_dir(version)
        active_id = version_service.get_active_profile_id(version)
        summaries: list[ProfileSummary] = []

        if not profiles_dir.is_dir():
            return active_id, summaries

        removed = prune_orphan_profile_dirs(profiles_dir)
        if removed:
            logger.info(
                "Removed orphan profile dirs for version {}: {}",
                version,
                ", ".join(removed),
            )

        profile_ids: list[str] = []
        for entry in sorted(profiles_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            profile_ids.append(entry.name)

        if active_id not in profile_ids:
            logger.warning(
                "Active profile {} missing for version {}, resetting to default",
                active_id,
                version,
            )
            active_id = DEFAULT_PROFILE_ID
            write_active_profile_id(profiles_dir, active_id)

        for profile_id in profile_ids:
            summaries.append(self._build_summary(version, profile_id, active_id))

        return active_id, summaries

    def get_profile(self, version: str, profile_id: str) -> ProfileSummary:
        version_service.ensure_profiles_layout(version)
        profile_dir = version_service.profile_dir(version, profile_id)
        if not profile_dir.is_dir():
            raise ProfileNotFoundError(version, profile_id)
        active_id = version_service.get_active_profile_id(version)
        return self._build_summary(version, profile_id, active_id)

    def create_profile(
        self,
        version: str,
        name: str,
        *,
        profile_id: str | None = None,
        source: ProfileSource = "manual",
        activate: bool = True,
    ) -> ProfileSummary:
        version_service.ensure_profiles_layout(version)
        resolved_id = validate_profile_id(profile_id) if profile_id else slug_profile_id(name)
        profile_dir = version_service.profile_dir(version, resolved_id)
        if profile_dir.exists():
            raise ProfileAlreadyExistsError(resolved_id)

        ensure_profile_subdirs(profile_dir)
        write_profile_meta(
            profile_dir,
            profile_id=resolved_id,
            name=name.strip(),
            source=source,
        )
        if activate:
            self.activate_profile(version, resolved_id)
        return self.get_profile(version, resolved_id)

    def activate_profile(self, version: str, profile_id: str) -> ProfileSummary:
        version_service.ensure_profiles_layout(version)
        profile_dir = version_service.profile_dir(version, profile_id)
        if not profile_dir.is_dir():
            raise ProfileNotFoundError(version, profile_id)
        write_active_profile_id(version_service.profiles_dir(version), profile_id)
        return self.get_profile(version, profile_id)

    def delete_profile(self, version: str, profile_id: str) -> None:
        if profile_id == DEFAULT_PROFILE_ID:
            raise ValueError("Нельзя удалить профиль по умолчанию")

        version_service.ensure_profiles_layout(version)
        profile_dir = version_service.profile_dir(version, profile_id)
        if not profile_dir.is_dir():
            raise ProfileNotFoundError(version, profile_id)

        active_id = version_service.get_active_profile_id(version)
        from app.services.profile_storage import profile_storage_key
        from app.services.mod_service import mod_service
        from app.recipes.manager import recipe_manager
        from app.indexer.mod_registry import registry

        storage_key = profile_storage_key(version, profile_id)
        logger.info("Deleting profile {} for version {}", profile_id, version)
        remove_profile_dir(profile_dir)
        if profile_dir.exists():
            raise OSError(
                f"Не удалось полностью удалить папку профиля: {profile_dir}. "
                "Возможно, файлы заняты другим процессом (JVM export)."
            )
        registry.clear_version(storage_key)
        recipe_manager.clear_mods_for_version(storage_key)
        mod_service._loaded_versions.discard(storage_key)

        if active_id == profile_id:
            write_active_profile_id(
                version_service.profiles_dir(version),
                DEFAULT_PROFILE_ID,
            )
        logger.info("Deleted profile {} for version {}", profile_id, version)

    def check_integrity(
        self,
        version: str,
        profile_id: str,
        *,
        source_path_override: str | None = None,
    ) -> IntegrityReport:
        self.get_profile(version, profile_id)
        return check_profile_integrity(
            version,
            profile_id,
            mc_version=version,
            source_path_override=source_path_override,
        )

    def sync_from_source(
        self,
        version: str,
        profile_id: str,
        *,
        source_path_override: str | None = None,
    ) -> tuple[ProfileSyncStats, IntegrityReport]:
        self.get_profile(version, profile_id)
        stats = sync_profile_from_source(
            version,
            profile_id,
            mc_version=version,
            source_path_override=source_path_override,
        )
        from app.services.mod_service import mod_service

        mod_service.force_reload_version(
            version,
            profile_id=profile_id,
            enrich_recipes=False,
        )
        report = check_profile_integrity(
            version,
            profile_id,
            mc_version=version,
            source_path_override=source_path_override,
        )
        return stats, report

    def import_modpack_zip(
        self,
        version: str,
        archive_path: Path,
        *,
        name: str | None = None,
        activate: bool = True,
    ) -> tuple[ProfileSummary, ModpackImportStats]:
        version_service.ensure_profiles_layout(version)
        if not archive_path.is_file():
            raise InvalidModpackError(f"Архив не найден: {archive_path}")

        detected = detect_modpack_version_from_zip(archive_path)
        if detected is not None and detected.minecraft_version != version:
            raise ModpackVersionMismatchError(
                version,
                detected.minecraft_version,
                detected.modpack_name,
            )

        display_name = (
            name or (detected.modpack_name if detected else None) or archive_path.stem
        ).strip() or "Модпак"
        profile_id = slug_profile_id(display_name)
        profile_dir = version_service.profile_dir(version, profile_id)
        if profile_dir.exists():
            profile_id = slug_profile_id(display_name)

        ensure_profile_subdirs(profile_dir)
        write_profile_meta(
            profile_dir,
            profile_id=profile_id,
            name=display_name,
            source="modpack_zip",
            loader=detected.loader if detected else None,
            forge_version=detected.forge_version if detected else None,
            source_archive=str(archive_path.resolve()),
        )

        try:
            with zipfile.ZipFile(archive_path) as archive:
                stats = self._import_from_zip_members(
                    archive,
                    profile_dir,
                    mc_version=version,
                )
        except zipfile.BadZipFile as exc:
            remove_profile_dir(profile_dir)
            raise InvalidModpackError("Некорректный zip-архив модпака") from exc

        if stats.jars_imported == 0:
            remove_profile_dir(profile_dir)
            raise InvalidModpackError(
                "В архиве не найдены .jar модов (ожидаются mods/ или overrides/mods/)"
            )

        if activate:
            self.activate_profile(version, profile_id)

        from app.services.mod_service import mod_service

        mod_service.force_reload_version(
            version,
            profile_id=profile_id,
            enrich_recipes=False,
        )

        return self.get_profile(version, profile_id), stats

    def import_from_instance_path(
        self,
        version: str,
        source_path: Path,
        *,
        name: str | None = None,
        activate: bool = True,
    ) -> tuple[ProfileSummary, ModpackImportStats, bool]:
        version_service.ensure_profiles_layout(version)
        raw_path = str(source_path).strip()
        resolved = resolve_host_filesystem_path(raw_path)
        if not resolved.is_dir():
            raise InvalidInstancePathError(f"Папка не найдена: {source_path}")

        detected = detect_modpack_version_from_directory(resolved)
        if detected is not None and detected.minecraft_version != version:
            raise ModpackVersionMismatchError(
                version,
                detected.minecraft_version,
                detected.modpack_name,
            )

        display_name = (
            name or (detected.modpack_name if detected else None) or resolved.name
        ).strip() or "Инстанс"
        profile_id = slug_profile_id(display_name)
        profile_dir = version_service.profile_dir(version, profile_id)
        if profile_dir.exists():
            profile_id = slug_profile_id(display_name)

        ensure_profile_subdirs(profile_dir)
        write_profile_meta(
            profile_dir,
            profile_id=profile_id,
            name=display_name,
            source="instance_path",
            loader=detected.loader if detected else None,
            forge_version=detected.forge_version if detected else None,
            source_path=raw_path,
        )

        stats = self._import_from_directory(resolved, profile_dir, mc_version=version)
        if stats.jars_imported == 0:
            remove_profile_dir(profile_dir)
            raise InvalidInstancePathError(
                "В папке не найдены .jar модов. Для Prism укажите корень инстанса "
                "(где mmc-pack.json) — моды обычно в minecraft/mods/. "
                "Также поддерживаются mods/ и overrides/mods/."
            )

        if activate:
            self.activate_profile(version, profile_id)

        from app.services.mod_service import mod_service

        mod_service.force_reload_version(
            version,
            profile_id=profile_id,
            enrich_recipes=False,
        )

        from app.services.recipe_bake_scheduler import schedule_neo_recipe_bake_after_import

        mc_for_layout = (
            detected.minecraft_version if detected is not None else version
        )
        bake_started = schedule_neo_recipe_bake_after_import(
            version,
            profile_id,
            source_path=raw_path,
            minecraft_version=mc_for_layout,
        )

        return self.get_profile(version, profile_id), stats, bake_started

    def _build_summary(
        self,
        version: str,
        profile_id: str,
        active_id: str,
    ) -> ProfileSummary:
        profile_dir = version_service.profile_dir(version, profile_id)
        meta = read_profile_meta(profile_dir)
        mods_dir = version_service.mods_dir(version, profile_id)
        return ProfileSummary(
            profile_id=str(meta.get("profile_id", profile_id)),
            name=str(meta.get("name", profile_id)),
            source=str(meta.get("source", "default")),  # type: ignore[arg-type]
            created_at=str(meta.get("created_at", utc_now_iso())),
            mod_count=count_mod_jars(mods_dir),
            active=profile_id == active_id,
            loader=str(meta["loader"]) if isinstance(meta.get("loader"), str) else None,
            forge_version=(
                str(meta["forge_version"])
                if isinstance(meta.get("forge_version"), str)
                else None
            ),
        )

    def _import_from_directory(
        self,
        source: Path,
        profile_dir: Path,
        *,
        mc_version: str,
    ) -> ModpackImportStats:
        roots = self._detect_content_roots(source, mc_version=mc_version, is_zip=False)
        return self._copy_profile_content(source, profile_dir, roots)

    def _import_from_zip_members(
        self,
        archive: zipfile.ZipFile,
        profile_dir: Path,
        *,
        mc_version: str,
    ) -> ModpackImportStats:
        names = archive.namelist()
        roots = self._detect_content_roots(names, mc_version=mc_version, is_zip=True)
        stats = ModpackImportStats(0, 0, 0)

        for member in names:
            if member.endswith("/"):
                continue
            pure = PurePosixPath(member)
            suffix = pure.suffix.lower()
            relative = self._relative_profile_path(member, roots, mc_version=mc_version)
            if relative is None:
                continue

            destination = profile_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

            if relative.parts[0] == "mods" and suffix == ".jar":
                stats = ModpackImportStats(
                    stats.jars_imported + 1,
                    stats.config_files_imported,
                    stats.script_files_imported,
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )
            elif relative.parts[0] == "config":
                stats = ModpackImportStats(
                    stats.jars_imported,
                    stats.config_files_imported + 1,
                    stats.script_files_imported,
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )
            elif relative.parts[0] == "scripts":
                stats = ModpackImportStats(
                    stats.jars_imported,
                    stats.config_files_imported,
                    stats.script_files_imported + 1,
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )

        kubejs_prefix = detect_kubejs_root(names, is_zip=True)
        if kubejs_prefix:
            kubejs_stats = copy_kubejs_from_zip_members(
                archive,
                names,
                kubejs_prefix,
                profile_dir / "kubejs",
            )
            stats = self._merge_kubejs_stats(stats, kubejs_stats)

        return stats

    def _import_mod_jars_flat(self, source: Path, mods_dir: Path) -> int:
        """Копирует все .jar из дерева источника в mods/ без подпапок."""
        mods_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for jar_path in sorted(source.rglob("*.jar")):
            if not jar_path.is_file():
                continue
            destination = mods_dir / jar_path.name
            shutil.copy2(jar_path, destination)
            count += 1
        return count

    def _copy_profile_content(
        self,
        source_root: Path,
        profile_dir: Path,
        roots: dict[str, str],
    ) -> ModpackImportStats:
        stats = ModpackImportStats(0, 0, 0)
        for category, prefix in roots.items():
            source = source_root / prefix
            if not source.exists():
                continue
            destination = profile_dir / category

            if category == "mods":
                jar_count = self._import_mod_jars_flat(source, destination)
                stats = ModpackImportStats(
                    jar_count,
                    stats.config_files_imported,
                    stats.script_files_imported,
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )
                continue

            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            if category == "config":
                stats = ModpackImportStats(
                    stats.jars_imported,
                    sum(1 for _ in destination.rglob("*") if _.is_file()),
                    stats.script_files_imported,
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )
            elif category == "scripts":
                stats = ModpackImportStats(
                    stats.jars_imported,
                    stats.config_files_imported,
                    sum(1 for _ in destination.rglob("*") if _.is_file()),
                    stats.kubejs_server_scripts_imported,
                    stats.kubejs_data_files_imported,
                    stats.kubejs_asset_files_imported,
                )

        kubejs_prefix = detect_kubejs_root(source_root, is_zip=False)
        if kubejs_prefix:
            kubejs_stats = copy_kubejs_from_directory(
                source_root / kubejs_prefix,
                profile_dir / "kubejs",
            )
            stats = self._merge_kubejs_stats(stats, kubejs_stats)

        return stats

    def _merge_kubejs_stats(
        self,
        stats: ModpackImportStats,
        kubejs_stats: KubejsImportStats,
    ) -> ModpackImportStats:
        return ModpackImportStats(
            stats.jars_imported,
            stats.config_files_imported,
            stats.script_files_imported,
            kubejs_stats.server_script_files,
            kubejs_stats.data_files,
            kubejs_stats.asset_files,
        )

    def _count_jars_under_prefix(
        self,
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
        self,
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

    def _detect_content_roots(
        self,
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
                        self._count_jars_under_prefix(source, path, is_zip=is_zip),
                        -path.count("/"),
                    ),
                )
            else:
                roots[category] = max(
                    matched,
                    key=lambda path: (
                        self._count_files_under_prefix(source, path, is_zip=is_zip),
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
                if self._count_jars_under_prefix(source_path, option, is_zip=False) > 0:
                    roots["mods"] = option
                    break
        return roots

    def _relative_profile_path(
        self,
        member: str,
        roots: dict[str, str],
        *,
        mc_version: str,
    ) -> Path | None:
        pure = PurePosixPath(member)

        for category, prefix in roots.items():
            prefix_path = PurePosixPath(prefix)
            try:
                relative = pure.relative_to(prefix_path)
            except ValueError:
                continue

            if category == "mods":
                if relative.suffix.lower() != ".jar":
                    continue
                # Forge читает только mods/*.jar — выравниваем в корень
                return Path("mods") / relative.name

            return Path(category) / Path(*relative.parts)

        return None


profile_service = ProfileService()
