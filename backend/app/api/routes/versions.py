from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path

from app.schemas.versions import (
    IngredientIndexResponse,
    ItemIconManifestResponse,
    RecipeExportStatusResponse,
    VersionCatalogEntryResponse,
    VersionCatalogResponse,
    VersionInstallResponse,
    VersionListResponse,
)
from app.schemas.mod_dependencies import ModDependencyDownloadResponse
from app.services.jvm_export_status_service import recipe_export_status_service
from app.schemas.vanilla_icons import VanillaIconRenderResponse
from app.services.minecraft_version_catalog import get_minecraft_version_catalog
from app.services.vanilla_icon_service import vanilla_icon_service
from app.services.mod_dependency_service import (
    ModDependencyDownloadError,
    mod_dependency_service,
)
from app.services.version_install_service import version_install_service
from app.services.version_service import version_service

router = APIRouter(prefix="/versions", tags=["versions"])


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


@router.get("/{version}/item-icons", response_model=ItemIconManifestResponse)
def list_item_icons(version: str) -> ItemIconManifestResponse:
    icons = version_service.list_item_icons(version)
    if not icons and version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    return ItemIconManifestResponse(
        version=version,
        icons=icons,
        revision=version_service.icons_revision(version),
    )


@router.get("/{version}/ingredient-index", response_model=IngredientIndexResponse)
def get_ingredient_index(version: str) -> IngredientIndexResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    payload = version_service.build_ingredient_index(version)
    return IngredientIndexResponse.model_validate(payload)


@router.get("/{version}/recipe-export-status", response_model=RecipeExportStatusResponse)
def get_recipe_export_status(version: str) -> RecipeExportStatusResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    status = recipe_export_status_service.refresh_manifest(version)
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


@router.post(
    "/{version}/download-missing-mod-dependencies",
    response_model=ModDependencyDownloadResponse,
)
def download_missing_mod_dependencies(version: str) -> ModDependencyDownloadResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    try:
        result = mod_dependency_service.download_missing_dependencies(version)
    except ModDependencyDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recipe_export_status_service.refresh_manifest(version)
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


@router.get("/{version}/items/{filename}", response_model=None)
def get_item_icon(version: str, filename: str) -> FileResponse | Response:
    resolved = version_service.resolve_item_icon(version, filename)
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


@router.post("/{version}/render-icons", response_model=VanillaIconRenderResponse)
def render_vanilla_icons(version: str) -> VanillaIconRenderResponse:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    if version_service.resolve_jar_path(version) is None:
        raise HTTPException(status_code=404, detail=f"Jar not found for version: {version}")

    result = vanilla_icon_service.ensure_icons(version)
    return VanillaIconRenderResponse(
        version=result.version,
        required=result.required,
        already_present=result.already_present,
        requested=result.requested,
        rendered=result.rendered,
        skipped=result.skipped,
        errors=result.errors,
    )
