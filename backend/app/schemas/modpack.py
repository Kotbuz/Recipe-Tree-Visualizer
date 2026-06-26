from __future__ import annotations

from pydantic import BaseModel, Field


class ModpackInspectResponse(BaseModel):
    minecraft_version: str
    modpack_name: str | None = None
    loader: str | None = None
    forge_version: str | None = None
    forge_installed: bool | None = None
    detection_source: str
    version_installed: bool
    catalog_available: bool


class ModpackInspectPathRequest(BaseModel):
    path: str = Field(min_length=1)


class PickFolderResponse(BaseModel):
    path: str | None = None
    cancelled: bool = False
