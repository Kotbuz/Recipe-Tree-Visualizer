from __future__ import annotations

from pydantic import BaseModel, Field


class JavaRuntimeResponse(BaseModel):
    major: int
    home: str
    java_executable: str
    label: str
    source: str


class JavaSettingsResponse(BaseModel):
    runtimes: list[JavaRuntimeResponse]
    selected: dict[str, str] = Field(default_factory=dict)


class SetJavaHomeRequest(BaseModel):
    major: int = Field(ge=8, le=23)
    home: str


class PickJavaResponse(BaseModel):
    home: str | None = None
    cancelled: bool = False
    major: int | None = None
