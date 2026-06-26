from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.parser.exceptions import JarParseError
from app.schemas.items import ModListResponse
from app.services.mod_service import (
    ModNotFoundError,
    ModProfileNotFoundError,
    ModUploadTooLargeError,
    ModVersionNotInstalledError,
    mod_service,
)

router = APIRouter(prefix="/mods", tags=["mods"])


@router.get("", response_model=ModListResponse)
def list_mods(
    version: str = Query(..., min_length=1),
    profile_id: str | None = Query(default=None, min_length=1),
) -> ModListResponse:
    return ModListResponse(
        mods=mod_service.list_mods(game_version=version, profile_id=profile_id),
    )


@router.post("/upload", response_model=ModListResponse)
async def upload_mods(
    files: list[UploadFile],
    version: str = Query(..., min_length=1),
    profile_id: str | None = Query(default=None, min_length=1),
) -> ModListResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one .jar file is required")
    for file in files:
        filename = (file.filename or "").lower()
        if not filename.endswith(".jar"):
            raise HTTPException(status_code=400, detail="Only .jar files are supported")
    try:
        await mod_service.upload_mods(files, version, profile_id=profile_id)
    except ModVersionNotInstalledError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Версия Minecraft не установлена: {exc.version}. "
                "Сначала установите её в менеджере версий."
            ),
        ) from exc
    except ModProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModUploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except JarParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ModListResponse(
        mods=mod_service.list_mods(game_version=version, profile_id=profile_id),
    )


@router.delete("", response_model=ModListResponse)
def delete_mod(
    version: str = Query(..., min_length=1),
    jar_filename: str = Query(..., min_length=1),
    profile_id: str | None = Query(default=None, min_length=1),
) -> ModListResponse:
    try:
        mod_service.delete_mod_jar(version, jar_filename, profile_id=profile_id)
    except ModVersionNotInstalledError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ModListResponse(
        mods=mod_service.list_mods(game_version=version, profile_id=profile_id),
    )
