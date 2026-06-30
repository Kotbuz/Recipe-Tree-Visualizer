from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.java_settings import (
    JavaRuntimeResponse,
    JavaSettingsResponse,
    PickJavaResponse,
    SetJavaHomeRequest,
)
from app.services import java_runtime_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/java", response_model=JavaSettingsResponse)
def get_java_settings() -> JavaSettingsResponse:
    runtimes = [
        JavaRuntimeResponse(
            major=runtime.major,
            home=runtime.home,
            java_executable=runtime.java_executable,
            label=runtime.label,
            source=runtime.source,
        )
        for runtime in java_runtime_service.discover_java_runtimes()
    ]
    selected = {
        str(major): home for major, home in java_runtime_service.get_configured_java_homes().items()
    }
    return JavaSettingsResponse(runtimes=runtimes, selected=selected)


@router.put("/java/{major}", response_model=JavaRuntimeResponse)
def set_java_home(major: int, body: SetJavaHomeRequest) -> JavaRuntimeResponse:
    if body.major != major:
        raise HTTPException(status_code=400, detail="major в URL и теле запроса должны совпадать")
    try:
        runtime = java_runtime_service.set_java_home(major, body.home)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JavaRuntimeResponse(
        major=runtime.major,
        home=runtime.home,
        java_executable=runtime.java_executable,
        label=runtime.label,
        source=runtime.source,
    )


@router.delete("/java/{major}", status_code=204)
def clear_java_home(major: int) -> None:
    java_runtime_service.clear_java_home(major)


@router.post("/java/pick", response_model=PickJavaResponse)
def pick_java_home() -> PickJavaResponse:
    if not get_settings().enable_local_folder_picker:
        raise HTTPException(
            status_code=404,
            detail="Выбор Java через проводник отключён (ENABLE_LOCAL_FOLDER_PICKER=false)",
        )
    try:
        selected_home = java_runtime_service.pick_java_home_dialog(
            title="Выберите java.exe (JDK для экспорта рецептов)",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось открыть диалог выбора Java: {exc}",
        ) from exc
    if not selected_home:
        return PickJavaResponse(home=None, cancelled=True, major=None)

    major = java_runtime_service.detect_java_major(Path(selected_home))
    return PickJavaResponse(home=selected_home, cancelled=False, major=major)
