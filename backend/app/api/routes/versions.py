from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path

from app.schemas.versions import (
    IngredientIndexResponse,
    ItemIconManifestResponse,
    VersionCatalogEntryResponse,
    VersionCatalogResponse,
    VersionInstallResponse,
    VersionListResponse,
)
from app.schemas.vanilla_icons import VanillaIconRenderResponse
from app.services.minecraft_version_catalog import get_minecraft_version_catalog
from app.services.vanilla_icon_service import vanilla_icon_service
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
