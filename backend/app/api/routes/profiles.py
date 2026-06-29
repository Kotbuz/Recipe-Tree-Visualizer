from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.schemas.profiles import (
    CreateProfileRequest,
    ImportModpackResponse,
    ImportPathRequest,
    IntegrityIssueResponse,
    ProfileIntegrityResponse,
    ProfileListResponse,
    ProfileResponse,
    ProfileSyncRequest,
    ProfileSyncResponse,
)
from app.services.profile_integrity import ProfileSyncSourceUnavailableError
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
        kubejs_server_scripts_imported=stats.kubejs_server_scripts_imported,
        kubejs_data_files_imported=stats.kubejs_data_files_imported,
        kubejs_asset_files_imported=stats.kubejs_asset_files_imported,
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
        kubejs_server_scripts_imported=stats.kubejs_server_scripts_imported,
        kubejs_data_files_imported=stats.kubejs_data_files_imported,
        kubejs_asset_files_imported=stats.kubejs_asset_files_imported,
    )


def _integrity_response(version: str, report) -> ProfileIntegrityResponse:
    return ProfileIntegrityResponse(
        version=version,
        profile_id=report.profile_id,
        source=report.source,  # type: ignore[arg-type]
        source_path=report.source_path,
        source_available=report.source_available,
        needs_source_path=report.needs_source_path,
        healthy=report.healthy,
        can_sync=report.can_sync,
        issues=[
            IntegrityIssueResponse(
                category=issue.category,
                status=issue.status,
                profile_count=issue.profile_count,
                source_count=issue.source_count,
                missing_count=issue.missing_count,
                message=issue.message,
            )
            for issue in report.issues
        ],
    )


@router.get("/{profile_id}/integrity", response_model=ProfileIntegrityResponse)
def check_profile_integrity_route(
    version: str,
    profile_id: str,
    source_path: str | None = Query(default=None, min_length=1),
) -> ProfileIntegrityResponse:
    _require_version(version)
    try:
        report = profile_service.check_integrity(
            version,
            profile_id,
            source_path_override=source_path,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _integrity_response(version, report)


@router.post("/{profile_id}/sync", response_model=ProfileSyncResponse)
def sync_profile_from_source_route(
    version: str,
    profile_id: str,
    body: ProfileSyncRequest | None = None,
) -> ProfileSyncResponse:
    _require_version(version)
    override = body.path.strip() if body and body.path else None
    try:
        stats, report = profile_service.sync_from_source(
            version,
            profile_id,
            source_path_override=override,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileSyncSourceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ProfileSyncResponse(
        version=version,
        profile_id=profile_id,
        jars_synced=stats.jars_synced,
        config_files_synced=stats.config_files_synced,
        script_files_synced=stats.script_files_synced,
        kubejs_server_scripts_synced=stats.kubejs_server_scripts_synced,
        kubejs_data_files_synced=stats.kubejs_data_files_synced,
        kubejs_asset_files_synced=stats.kubejs_asset_files_synced,
        integrity=_integrity_response(version, report),
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
