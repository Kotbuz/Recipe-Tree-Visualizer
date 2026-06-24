from fastapi import APIRouter, HTTPException, UploadFile

from app.parser.exceptions import JarParseError
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
    for file in files:
        filename = (file.filename or "").lower()
        if not filename.endswith(".jar"):
            raise HTTPException(status_code=400, detail="Only .jar files are supported")
    try:
        await mod_service.upload_mods(files)
    except JarParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ModListResponse(mods=mod_service.list_mods())


@router.post("/modpack", response_model=ModListResponse)
async def upload_modpack(file: UploadFile) -> ModListResponse:
    try:
        mod_service.upload_modpack(file.filename or "modpack.zip")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return ModListResponse(mods=mod_service.list_mods())
