from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas.items import ModListResponse
from app.services.mod_service import mod_service

router = APIRouter(prefix="/mods", tags=["mods"])


@router.get("", response_model=ModListResponse)
def list_mods() -> ModListResponse:
    return ModListResponse(mods=mod_service.list_mods())


@router.post("/upload", response_model=ModListResponse)
async def upload_mods(files: list[UploadFile]) -> ModListResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one .jar file is required")
    try:
        # Placeholder until parser stores uploads on disk.
        jar_paths = [file.filename or "unknown.jar" for file in files]
        mod_service.upload_mods(jar_paths)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return ModListResponse(mods=mod_service.list_mods())


@router.post("/modpack", response_model=ModListResponse)
async def upload_modpack(file: UploadFile) -> ModListResponse:
    try:
        mod_service.upload_modpack(file.filename or "modpack.zip")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return ModListResponse(mods=mod_service.list_mods())
