from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.versions import ItemIconManifestResponse, VersionListResponse
from app.services.version_service import version_service

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("", response_model=VersionListResponse)
@router.get("/", response_model=VersionListResponse, include_in_schema=False)
def list_versions() -> VersionListResponse:
    return VersionListResponse(versions=version_service.list_versions())


@router.get("/{version}/item-icons", response_model=ItemIconManifestResponse)
def list_item_icons(version: str) -> ItemIconManifestResponse:
    icons = version_service.list_item_icons(version)
    if not icons and version not in version_service.list_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    return ItemIconManifestResponse(version=version, icons=icons)


@router.get("/{version}/items/{filename}")
def get_item_icon(version: str, filename: str) -> FileResponse:
    icon_path = version_service.resolve_item_icon_path(version, filename)
    if icon_path is None:
        raise HTTPException(status_code=404, detail="Icon not found")
    return FileResponse(icon_path, media_type="image/png")
