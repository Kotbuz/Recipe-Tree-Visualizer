from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProfileSource = Literal["default", "modpack_zip", "instance_path", "manual"]


class ProfileSummary(BaseModel):
    profile_id: str
    name: str
    source: ProfileSource = "default"
    created_at: str
    mod_count: int = 0
    active: bool = False
    loader: str | None = None
    forge_version: str | None = None
    minecraft_version: str | None = None
    source_path: str | None = None


class ProfileListResponse(BaseModel):
    version: str
    active_profile_id: str
    profiles: list[ProfileSummary]


class ProfileResponse(BaseModel):
    version: str
    profile: ProfileSummary


class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_id: str | None = Field(default=None, min_length=1, max_length=64)


class ImportPathRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)


class ImportModpackResponse(BaseModel):
    version: str
    profile: ProfileSummary
    jars_imported: int
    config_files_imported: int
    script_files_imported: int
    kubejs_server_scripts_imported: int = 0
    kubejs_data_files_imported: int = 0
    kubejs_asset_files_imported: int = 0
    recipe_bake_started: bool = False


class IntegrityIssueResponse(BaseModel):
    category: str
    status: str
    profile_count: int
    source_count: int
    missing_count: int
    message: str


class ProfileSyncRequest(BaseModel):
    path: str | None = Field(default=None, min_length=1)


class ProfileIntegrityResponse(BaseModel):
    version: str
    profile_id: str
    source: ProfileSource
    source_path: str | None = None
    source_available: bool
    needs_source_path: bool = False
    healthy: bool
    can_sync: bool
    issues: list[IntegrityIssueResponse]


class ProfileSyncResponse(BaseModel):
    version: str
    profile_id: str
    jars_synced: int = 0
    config_files_synced: int = 0
    script_files_synced: int = 0
    kubejs_server_scripts_synced: int = 0
    kubejs_data_files_synced: int = 0
    kubejs_asset_files_synced: int = 0
    integrity: ProfileIntegrityResponse
