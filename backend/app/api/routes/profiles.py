from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.schemas.profiles import (
    CreateProfileRequest,
    ImportModpackResponse,
    ImportPathRequest,
    ProfileListResponse,
    ProfileResponse,
)
from app.services.profile_service import (
    InvalidInstancePathError,
    InvalidModpackError,
    ModpackVersionMismatchError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    profile_service,
)
from app.services.profile_storage import validate_profile_id
from app.services.version_service import version_service

router = APIRouter(prefix="/versions/{version}/profiles", tags=["profiles"])


def _require_version(version: str) -> None:
    if version not in version_service.list_installed_versions():
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")


@router.get("", response_model=ProfileListResponse)
def list_profiles(version: str) -> ProfileListResponse:
    _require_version(version)
    active_id, profiles = profile_service.list_profiles(version)
    return ProfileListResponse(
        version=version,
        active_profile_id=active_id,
        profiles=profiles,
    )


@router.post("", response_model=ProfileResponse)
def create_profile(version: str, body: CreateProfileRequest) -> ProfileResponse:
    _require_version(version)
    try:
        if body.profile_id:
            validate_profile_id(body.profile_id)
        profile = profile_service.create_profile(
            version,
            body.name,
            profile_id=body.profile_id,
            activate=True,
        )
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProfileResponse(version=version, profile=profile)


@router.post("/import-modpack", response_model=ImportModpackResponse)
async def import_modpack(
    version: str,
    file: UploadFile,
    name: str | None = Query(default=None, min_length=1, max_length=120),
) -> ImportModpackResponse:
    _require_version(version)
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается .zip архив модпака")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        profile, stats = profile_service.import_modpack_zip(
            version,
            tmp_path,
            name=name or Path(file.filename or "modpack.zip").stem,
        )
    except ModpackVersionMismatchError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "requested_version": exc.requested_version,
                "detected_version": exc.detected_version,
                "modpack_name": exc.modpack_name,
            },
        ) from exc
    except InvalidModpackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return ImportModpackResponse(
        version=version,
        profile=profile,
        jars_imported=stats.jars_imported,
        config_files_imported=stats.config_files_imported,
        script_files_imported=stats.script_files_imported,
    )


@router.post("/import-path", response_model=ImportModpackResponse)
def import_from_path(version: str, body: ImportPathRequest) -> ImportModpackResponse:
    _require_version(version)
    try:
        profile, stats = profile_service.import_from_instance_path(
            version,
            Path(body.path),
            name=body.name,
        )
    except ModpackVersionMismatchError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "requested_version": exc.requested_version,
                "detected_version": exc.detected_version,
                "modpack_name": exc.modpack_name,
            },
        ) from exc
    except InvalidInstancePathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImportModpackResponse(
        version=version,
        profile=profile,
        jars_imported=stats.jars_imported,
        config_files_imported=stats.config_files_imported,
        script_files_imported=stats.script_files_imported,
    )


@router.post("/{profile_id}/activate", response_model=ProfileResponse)
def activate_profile(version: str, profile_id: str) -> ProfileResponse:
    _require_version(version)
    try:
        profile = profile_service.activate_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProfileResponse(version=version, profile=profile)


@router.delete("/{profile_id}", response_model=ProfileListResponse)
def delete_profile(version: str, profile_id: str) -> ProfileListResponse:
    _require_version(version)
    try:
        profile_service.delete_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    active_id, profiles = profile_service.list_profiles(version)
    return ProfileListResponse(
        version=version,
        active_profile_id=active_id,
        profiles=profiles,
    )
