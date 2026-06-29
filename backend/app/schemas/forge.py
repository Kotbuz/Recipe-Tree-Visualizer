from __future__ import annotations

from pydantic import BaseModel, Field


class ForgePrepareRequest(BaseModel):
    forge_build: str = Field(min_length=1, max_length=32)


class ForgeInstallStatusResponse(BaseModel):
    minecraft_version: str
    forge_build: str
    installed: bool
    running: bool
    phase: str
    message: str
    progress: int = Field(ge=0, le=100)
    error: str | None = None
