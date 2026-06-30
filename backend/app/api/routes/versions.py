from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, Response
from loguru import logger

from app.recipes.loaders.recipe_paths import recipe_layout_for_version
from app.schemas.forge import ForgeInstallStatusResponse, ForgePrepareRequest
from app.schemas.mod_dependencies import ModDependencyDownloadResponse
from app.schemas.vanilla_icons import VanillaIconRenderResponse
from app.schemas.versions import (
    ClearRecipeExportResponse,
    IngredientIndexResponse,
    ItemIconManifestResponse,
    RecipeExportStatusResponse,
    ReloadModsResponse,
    VersionCatalogEntryResponse,
    VersionCatalogResponse,
    VersionInstallResponse,
    VersionListResponse,
)
from app.services.forge_install_service import ForgeInstallError, forge_install_service
from app.services.jvm_export_status_service import (
    RecipeExportStatus,
    _extract_forge_loader_errors,
    _forge_log_path,
    recipe_export_status_service,
)
from app.services.jvm_recipe_export_service import JvmRecipeExportError, jvm_recipe_export_service
from app.services.minecraft_version_catalog import get_minecraft_version_catalog
from app.services.mod_dependency_service import (
    ModDependencyDownloadError,
    mod_dependency_service,
)
from app.services.mod_service import ModVersionNotInstalledError, mod_service
from app.services.vanilla_icon_service import vanilla_icon_service
from app.services.version_install_service import version_install_service
from app.services.version_service import version_service

router = APIRouter(prefix="/versions", tags=["versions"])


def _export_status_response(status: RecipeExportStatus) -> RecipeExportStatusResponse:
    return RecipeExportStatusResponse(
        version=status.version,
        layout=status.layout,
        exported_recipe_count=status.exported_recipe_count,
        installed_mod_jars=list(status.installed_mod_jars),
        recipe_mod_ids=list(status.recipe_mod_ids),
        mods_without_recipes=list(status.mods_without_recipes),
        missing_dependencies=[
            {
                "mod_id": issue.mod_id,
                "jar_name": issue.jar_name,
                "requires": list(issue.missing_dependencies),
            }
            for issue in status.missing_dependencies
        ],
        warnings=list(status.warnings),
        log_errors=list(status.log_errors),
    )


@router.get("", response_model=VersionListResponse)
@router.get("/", response_model=VersionListResponse, include_in_schema=False)
def list_installed_versions() -> VersionListResponse:
    return VersionListResponse(versions=version_service.list_installed_versions())


@router.get("/catalog", response_model=VersionCatalogResponse)
def list_version_catalog() -> VersionCatalogResponse:
    installed = set(version_service.list_installed_versions())
    try:
        catalog_entries = get_minecraft_version_catalog().list_releases()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Version catalog is temporarily unavailable: {exc}",
        ) from exc

    releases = [
        VersionCatalogEntryResponse(version=entry.version, installed=entry.version in installed)
        for entry in catalog_entries
    ]
    return VersionCatalogResponse(releases=releases)


@router.post("/{version}/install", response_model=VersionInstallResponse)
def install_version(version: str) -> VersionInstallResponse:
    if version_service.is_version_installed(version):
        raise HTTPException(status_code=409, detail=f"Version already installed: {version}")

    try:
        result = version_install_service.install(version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to install version: {exc}") from exc

    return VersionInstallResponse(
        version=result.version,
        client_jar_path=result.client_jar_path,
        icons_rendered=result.icons_rendered,
        icon_errors=list(result.icon_errors),
    )


def _forge_status_response(status) -> ForgeInstallStatusResponse:
    return ForgeInstallStatusResponse(
        minecraft_version=status.minecraft_version,
        forge_build=status.forge_build,
        installed=status.installed,
        running=status.running,
        phase=status.phase,
        message=status.message,
        progress=status.progress,
        error=status.error,
    )


@router.get("/{version}/forge/install-status", response_model=ForgeInstallStatusResponse)
def get_forge_install_status(
    version: str,
    forge_build: str = Query(min_length=1, max_length=32),
) -> ForgeInstallStatusResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    status = forge_install_service.get_status(version, forge_build)
    return _forge_status_response(status)


@router.post("/{version}/forge/prepare", response_model=ForgeInstallStatusResponse)
def prepare_forge_install(
    version: str,
    body: ForgePrepareRequest,
) -> ForgeInstallStatusResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    try:
        status = forge_install_service.prepare(version, body.forge_build)
    except ForgeInstallError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _forge_status_response(status)


@router.get("/{version}/item-icons", response_model=ItemIconManifestResponse)
def list_item_icons(
    version: str,
    background_tasks: BackgroundTasks,
    profile_id: str | None = Query(default=None, min_length=1),
) -> ItemIconManifestResponse:
    if version in version_service.list_installed_versions():
        icons_preview = version_service.list_item_icons(version, profile_id=profile_id)
        if not icons_preview and version_service.resolve_jar_path(version) is not None:
            background_tasks.add_task(
                vanilla_icon_service.ensure_icons,
                version,
                profile_id=profile_id,
            )

    icons = version_service.list_item_icons(version, profile_id=profile_id)
    if not icons and version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    return ItemIconManifestResponse(
        version=version,
        icons=icons,
        revision=version_service.icons_revision(version, profile_id=profile_id),
    )


@router.get("/{version}/ingredient-index", response_model=IngredientIndexResponse)
def get_ingredient_index(version: str) -> IngredientIndexResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    payload = version_service.build_ingredient_index(version)
    return IngredientIndexResponse.model_validate(payload)


@router.get("/{version}/recipe-export-status", response_model=RecipeExportStatusResponse)
def get_recipe_export_status(
    version: str,
    profile_id: str | None = Query(default=None, min_length=1),
) -> RecipeExportStatusResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    status = recipe_export_status_service.refresh_manifest(version, profile_id=profile_id)
    return _export_status_response(status)


@router.post(
    "/{version}/download-missing-mod-dependencies",
    response_model=ModDependencyDownloadResponse,
)
def download_missing_mod_dependencies(
    version: str,
    profile_id: str | None = Query(default=None, min_length=1),
) -> ModDependencyDownloadResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    try:
        result = mod_dependency_service.download_missing_dependencies(
            version,
            profile_id=profile_id,
        )
    except ModDependencyDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recipe_export_status_service.refresh_manifest(version, profile_id=profile_id)
    return ModDependencyDownloadResponse(
        version=result.version,
        requested=list(result.requested),
        results=[
            {
                "dependency": item.dependency,
                "status": item.status,
                "jar_name": item.jar_name,
                "source": item.source,
                "manual_url": item.manual_url,
                "error": item.error,
            }
            for item in result.results
        ],
        all_resolved=result.all_resolved,
        export_triggered=result.export_triggered,
        export_recipe_count=result.export_recipe_count,
        export_error=result.export_error,
    )


@router.post("/{version}/reload-mods", response_model=ReloadModsResponse)
def reload_mods(
    version: str,
    trigger_export: bool = Query(default=True),
    profile_id: str | None = Query(default=None, min_length=1),
) -> ReloadModsResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    try:
        summaries = mod_service.force_reload_version(version, profile_id=profile_id)
    except ModVersionNotInstalledError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if trigger_export and recipe_layout_for_version(version) == "jvm":
        export_recipe_count: int | None = None
        export_error: str | None = None
        try:
            export_recipe_count = jvm_recipe_export_service.ensure_exported(
                version,
                profile_id=profile_id,
            )
            if export_recipe_count == 0:
                loader_errors = _extract_forge_loader_errors(
                    _forge_log_path(version), version=version
                )
                if loader_errors:
                    export_error = loader_errors[0]
                else:
                    export_error = "Экспорт завершился без файлов рецептов."
        except JvmRecipeExportError as exc:
            export_error = str(exc)
            logger.warning("Recipe export during reload failed for {}: {}", version, exc)
    else:
        export_recipe_count = None
        export_error = None

    status = recipe_export_status_service.refresh_manifest(version, profile_id=profile_id)
    return ReloadModsResponse(
        version=version,
        mod_count=len(summaries),
        export_status=_export_status_response(status),
        export_recipe_count=export_recipe_count,
        export_error=export_error,
    )


@router.post("/{version}/clear-recipe-export", response_model=ClearRecipeExportResponse)
def clear_recipe_export(
    version: str,
    include_ore_dict: bool = Query(default=True),
    profile_id: str | None = Query(default=None, min_length=1),
) -> ClearRecipeExportResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    try:
        deleted, ore_dict_removed = jvm_recipe_export_service.clear_exported_recipes(
            version,
            profile_id=profile_id,
            include_ore_dict=include_ore_dict,
        )
    except JvmRecipeExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recipe_export_status_service.refresh_manifest(version, profile_id=profile_id)
    return ClearRecipeExportResponse(
        version=version,
        deleted_recipe_files=deleted,
        ore_dict_removed=ore_dict_removed,
    )


@router.get("/{version}/items/{filename}", response_model=None)
def get_item_icon(
    version: str,
    filename: str,
    profile_id: str | None = Query(default=None, min_length=1),
) -> FileResponse | Response:
    resolved = version_service.resolve_item_icon(version, filename, profile_id=profile_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Icon not found")

    kind, payload = resolved
    if kind == "file":
        if not isinstance(payload, Path):
            raise HTTPException(status_code=500, detail="Invalid icon payload")
        return FileResponse(payload, media_type="image/png")

    if not isinstance(payload, bytes):
        raise HTTPException(status_code=500, detail="Invalid icon payload")
    return Response(content=payload, media_type="image/png")


@router.get("/{version}/blocks/{filename}", response_model=None)
def get_block_texture(
    version: str,
    filename: str,
    profile_id: str | None = Query(default=None, min_length=1),
) -> FileResponse:
    texture_path = version_service.resolve_block_texture_path(
        version,
        filename,
        profile_id=profile_id,
    )
    if texture_path is None:
        raise HTTPException(status_code=404, detail="Block texture not found")
    return FileResponse(texture_path, media_type="image/png")


@router.post("/{version}/render-icons", response_model=VanillaIconRenderResponse)
def render_vanilla_icons(
    version: str,
    profile_id: str | None = Query(default=None, min_length=1),
) -> VanillaIconRenderResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    if version_service.resolve_jar_path(version) is None:
        raise HTTPException(status_code=404, detail=f"Jar not found for version: {version}")

    result = vanilla_icon_service.ensure_icons(version, profile_id=profile_id)
    return VanillaIconRenderResponse(
        version=result.version,
        required=result.required,
        already_present=result.already_present,
        requested=result.requested,
        rendered=result.rendered,
        skipped=result.skipped,
        errors=result.errors,
    )
