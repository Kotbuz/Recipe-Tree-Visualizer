from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas.modpack import (
    ModpackInspectPathRequest,
    ModpackInspectResponse,
    PickFolderResponse,
)
from app.services.folder_picker import pick_folder_dialog
from app.services.minecraft_version_catalog import get_minecraft_version_catalog
from app.services.modpack_version_detector import (
    detect_modpack_version_from_directory,
    detect_modpack_version_from_zip,
)
from app.services.forge_install_service import forge_install_service
from app.services.version_service import version_service

router = APIRouter(prefix="/modpack", tags=["modpack"])


def _build_inspect_response(info) -> ModpackInspectResponse:
    installed = version_service.is_version_installed(info.minecraft_version)
    catalog_available = get_minecraft_version_catalog().get_release(info.minecraft_version) is not None
    forge_installed = (
        forge_install_service.is_installed(info.minecraft_version, info.forge_version)
        if info.forge_version and info.loader == "forge"
        else None
    )
    return ModpackInspectResponse(
        minecraft_version=info.minecraft_version,
        modpack_name=info.modpack_name,
        loader=info.loader,
        forge_version=info.forge_version,
        forge_installed=forge_installed,
        detection_source=info.detection_source,
        version_installed=installed,
        catalog_available=catalog_available,
    )


@router.post("/inspect", response_model=ModpackInspectResponse)
async def inspect_modpack_zip(file: UploadFile) -> ModpackInspectResponse:
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается .zip архив модпака")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        info = detect_modpack_version_from_zip(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if info is None:
        raise HTTPException(
            status_code=422,
            detail="Не удалось определить версию Minecraft в архиве модпака",
        )
    return _build_inspect_response(info)


@router.post("/inspect-path", response_model=ModpackInspectResponse)
def inspect_modpack_path(body: ModpackInspectPathRequest) -> ModpackInspectResponse:
    info = detect_modpack_version_from_directory(Path(body.path))
    if info is None:
        raise HTTPException(
            status_code=422,
            detail="Не удалось определить версию Minecraft в папке инстанса",
        )
    return _build_inspect_response(info)


@router.post("/pick-folder", response_model=PickFolderResponse)
def pick_instance_folder() -> PickFolderResponse:
    if not get_settings().enable_local_folder_picker:
        raise HTTPException(
            status_code=404,
            detail="Выбор папки через проводник отключён (ENABLE_LOCAL_FOLDER_PICKER=false)",
        )
    try:
        selected = pick_folder_dialog(title="Папка инстанса Prism / CurseForge")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось открыть диалог выбора папки: {exc}",
        ) from exc
    if not selected:
        return PickFolderResponse(path=None, cancelled=True)
    return PickFolderResponse(path=selected, cancelled=False)
