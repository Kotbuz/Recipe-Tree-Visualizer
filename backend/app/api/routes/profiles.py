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
from app.schemas.recipe_bake import (
    AssetRenderProgressResponse,
    AssetRenderStartResponse,
    AssetTaskProgress,
    RecipeBakeRequest,
    RecipeBakeResponse,
    RecipeBakeStatusResponse,
    RecipeStatsResponse,
)
from app.services.asset_render_service import asset_render_service
from app.services.neo_recipe_export_service import NeoRecipeExportError, neo_recipe_export_service
from app.services.profile_integrity import ProfileSyncSourceUnavailableError
from app.services.profile_service import (
    InvalidInstancePathError,
    InvalidModpackError,
    ModpackVersionMismatchError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    profile_service,
)
from app.services.profile_storage import DEFAULT_PROFILE_ID, validate_profile_id
from app.services.recipe_snapshot_service import read_snapshot_status
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
        profile, stats, bake_started = profile_service.import_from_instance_path(
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
        recipe_bake_started=bake_started,
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


@router.get("/{profile_id}/bake-recipes/status", response_model=RecipeBakeStatusResponse)
def recipe_bake_status(version: str, profile_id: str) -> RecipeBakeStatusResponse:
    _require_version(version)
    try:
        profile_service.get_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    status = neo_recipe_export_service.get_status(version, profile_id)
    return RecipeBakeStatusResponse(
        version=version,
        profile_id=profile_id,
        has_snapshot=bool(status.get("has_snapshot")),
        recipe_count=int(status.get("recipe_count", 0)),
        item_count=int(status.get("item_count", 0)),
        exported_at=status.get("exported_at"),
        minecraft_version=status.get("minecraft_version"),
        loader_version=status.get("loader_version"),
        last_error=status.get("last_error"),
        export_running=bool(neo_recipe_export_service.get_exporter_busy()),
    )


@router.get("/{profile_id}/recipe-stats", response_model=RecipeStatsResponse)
def recipe_stats(version: str, profile_id: str) -> RecipeStatsResponse:
    """Статус `Nр · Mп` под профилем: vanilla — из каталога, модпак — из снимка (I2)."""
    _require_version(version)
    try:
        profile_service.get_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if profile_id == DEFAULT_PROFILE_ID:
        from app.recipes.manager import recipe_manager

        recipes = recipe_manager.get_version_recipes(
            version, profile_id=profile_id, include_mods=True, include_synthetic=True
        )
        item_ids: set[str] = set()
        for recipe in recipes:
            for part in [*recipe.inputs, *recipe.outputs]:
                item_ids.add(part.item_id)
        return RecipeStatsResponse(
            version=version,
            profile_id=profile_id,
            has_stats=True,
            recipe_count=len(recipes),
            item_count=len(item_ids),
            source="catalog",
        )

    snapshot = read_snapshot_status(version, profile_id)
    if snapshot.has_snapshot:
        return RecipeStatsResponse(
            version=version,
            profile_id=profile_id,
            has_stats=True,
            recipe_count=snapshot.recipe_count,
            item_count=snapshot.item_count,
            source="snapshot",
        )
    return RecipeStatsResponse(
        version=version,
        profile_id=profile_id,
        has_stats=False,
        source="none",
    )


@router.get("/{profile_id}/asset-progress", response_model=AssetRenderProgressResponse)
def asset_render_progress(version: str, profile_id: str) -> AssetRenderProgressResponse:
    _require_version(version)
    state = asset_render_service.get_state(version, profile_id)
    return AssetRenderProgressResponse(
        version=version,
        profile_id=profile_id,
        running=state.running,
        icons=AssetTaskProgress(**state.icons.as_dict()),
        blocks=AssetTaskProgress(**state.blocks.as_dict()),
    )


@router.post("/{profile_id}/render-assets", response_model=AssetRenderStartResponse)
def start_asset_render(version: str, profile_id: str) -> AssetRenderStartResponse:
    """Кнопка «Рендер иконок» — полный повторный скан jar (L3), фоново."""
    _require_version(version)
    try:
        profile = profile_service.get_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Модпак без указанной папки инстанса не рендерим (Z1); vanilla/default — можно без неё.
    if profile_id != DEFAULT_PROFILE_ID and not profile.source_path:
        raise HTTPException(status_code=422, detail="Укажите папку инстанса")

    started = asset_render_service.start(version, profile_id, full_rescan=True)
    return AssetRenderStartResponse(version=version, profile_id=profile_id, started=started)


@router.post("/{profile_id}/bake-recipes", response_model=RecipeBakeResponse)
def bake_profile_recipes(
    version: str,
    profile_id: str,
    body: RecipeBakeRequest | None = None,
) -> RecipeBakeResponse:
    _require_version(version)
    try:
        profile_service.get_profile(version, profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    request = body or RecipeBakeRequest()
    try:
        result = neo_recipe_export_service.bake_profile(
            version,
            profile_id,
            force=request.force,
            source_path_override=request.source_path,
        )
    except NeoRecipeExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    status_code = result.get("status", "error")
    return RecipeBakeResponse(
        version=version,
        profile_id=profile_id,
        status=status_code,
        recipe_count=int(result.get("recipe_count", 0)),
        item_count=int(result.get("item_count", 0)),
        duration_seconds=result.get("duration_seconds"),
        log_tail=result.get("log_tail"),
        error=result.get("error"),
        kept_previous_snapshot=bool(result.get("kept_previous_snapshot")),
        backend_log_path=result.get("backend_log_path"),
        bake_log_path=result.get("bake_log_path"),
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
