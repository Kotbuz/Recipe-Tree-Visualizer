from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from app.core.config import get_settings
from app.mod_deps.catalog import catalog_entry_for, load_dependency_catalog
from app.mod_deps.curseforge import CurseForgeClient
from app.mod_deps.modrinth import ModrinthClient
from app.mod_deps.resolver import ModDependencyResolver
from app.recipes.loaders.recipe_paths import recipe_layout_for_version
from app.services.jvm_export_status_service import analyze_recipe_export_status
from app.services.jvm_recipe_export_service import JvmRecipeExportError, jvm_recipe_export_service
from app.services.mod_service import mod_service
from app.services.version_service import version_service


class ModDependencyDownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class DependencyDownloadResult:
    dependency: str
    status: str
    jar_name: str | None = None
    source: str | None = None
    manual_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ModDependencyDownloadResponse:
    version: str
    requested: tuple[str, ...]
    results: tuple[DependencyDownloadResult, ...]
    all_resolved: bool
    export_triggered: bool
    export_recipe_count: int | None = None
    export_error: str | None = None


class ModDependencyService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def download_missing_dependencies(self, version: str) -> ModDependencyDownloadResponse:
        if version not in version_service.list_installed_versions():
            raise ModDependencyDownloadError(f"Version not installed: {version}")

        if recipe_layout_for_version(version) != "jvm":
            raise ModDependencyDownloadError(
                f"Automatic dependency download is only supported for JVM layout versions (got {version})"
            )

        missing = _collect_missing_dependencies(version)
        if not missing:
            return ModDependencyDownloadResponse(
                version=version,
                requested=(),
                results=(),
                all_resolved=True,
                export_triggered=False,
            )

        resolver = self._build_resolver()
        mods_dir = version_service.mods_dir(version)
        mods_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = self._cache_dir(version)

        results: list[DependencyDownloadResult] = []
        for dependency_name in missing:
            results.append(
                self._download_one(
                    version=version,
                    dependency_name=dependency_name,
                    resolver=resolver,
                    mods_dir=mods_dir,
                    cache_dir=cache_dir,
                )
            )

        all_resolved = all(result.status == "downloaded" for result in results)
        export_triggered = False
        export_recipe_count: int | None = None
        export_error: str | None = None

        if all_resolved:
            mod_service.force_reload_version(version)
            try:
                export_recipe_count = jvm_recipe_export_service.ensure_exported(
                    version,
                    force=True,
                )
                export_triggered = True
            except JvmRecipeExportError as exc:
                export_error = str(exc)
                logger.warning("Recipe export after dependency download failed: {}", exc)
        elif any(result.status == "downloaded" for result in results):
            mod_service.force_reload_version(version)

        return ModDependencyDownloadResponse(
            version=version,
            requested=missing,
            results=tuple(results),
            all_resolved=all_resolved,
            export_triggered=export_triggered,
            export_recipe_count=export_recipe_count,
            export_error=export_error,
        )

    def _download_one(
        self,
        *,
        version: str,
        dependency_name: str,
        resolver: ModDependencyResolver,
        mods_dir: Path,
        cache_dir: Path,
    ) -> DependencyDownloadResult:
        catalog = load_dependency_catalog(version)
        entry = catalog_entry_for(catalog, dependency_name)
        resolution = resolver.resolve(entry=entry, game_version=version)

        if resolution.resolved is None:
            return DependencyDownloadResult(
                dependency=dependency_name,
                status="failed",
                manual_url=resolution.manual_url,
                error=resolution.error,
            )

        resolved = resolution.resolved
        destination = mods_dir / resolved.file_name
        if destination.is_file():
            return DependencyDownloadResult(
                dependency=dependency_name,
                status="already_present",
                jar_name=resolved.file_name,
                source=resolved.source,
                manual_url=resolution.manual_url,
            )

        dep_cache = cache_dir / _safe_dir_name(dependency_name)
        dep_cache.mkdir(parents=True, exist_ok=True)
        cached = dep_cache / resolved.file_name

        try:
            if not cached.is_file():
                self._download_file(resolved.download_url, cached)
            shutil.copy2(cached, destination)
        except Exception as exc:
            return DependencyDownloadResult(
                dependency=dependency_name,
                status="failed",
                manual_url=resolution.manual_url,
                error=str(exc),
            )

        logger.info(
            "Downloaded dependency {} for {} as {} ({})",
            dependency_name,
            version,
            resolved.file_name,
            resolved.source,
        )
        return DependencyDownloadResult(
            dependency=dependency_name,
            status="downloaded",
            jar_name=resolved.file_name,
            source=resolved.source,
            manual_url=resolution.manual_url,
        )

    def _download_file(self, url: str, destination: Path) -> None:
        timeout = httpx.Timeout(self._settings.mod_dependency_download_timeout_seconds)
        headers = {"User-Agent": self._settings.curseforge_user_agent}
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)

    def _build_resolver(self) -> ModDependencyResolver:
        timeout = self._settings.mod_dependency_download_timeout_seconds
        user_agent = self._settings.curseforge_user_agent
        return ModDependencyResolver(
            modrinth=ModrinthClient(timeout=timeout, user_agent=user_agent),
            curseforge=CurseForgeClient(
                api_key=self._settings.curseforge_api_key,
                user_agent=user_agent,
                timeout=timeout,
            ),
        )

    def _cache_dir(self, version: str) -> Path:
        return self._settings.minecraft_versions_path / ".cache" / "mod-deps" / version


def _collect_missing_dependencies(version: str) -> tuple[str, ...]:
    status = analyze_recipe_export_status(version)
    names: list[str] = []
    seen: set[str] = set()
    for issue in status.missing_dependencies:
        for dependency in issue.missing_dependencies:
            if dependency not in seen:
                seen.add(dependency)
                names.append(dependency)
    return tuple(names)


def _safe_dir_name(value: str) -> str:
    return value.replace("|", "_").replace("/", "_").replace("\\", "_")


mod_dependency_service = ModDependencyService()
