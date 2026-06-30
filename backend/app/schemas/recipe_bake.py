from __future__ import annotations

from pydantic import BaseModel, Field


class RecipeBakeStatusResponse(BaseModel):
    version: str
    profile_id: str
    has_snapshot: bool
    recipe_count: int = 0
    item_count: int = 0
    exported_at: str | None = None
    minecraft_version: str | None = None
    loader_version: str | None = None
    last_error: str | None = None
    export_running: bool = False


class RecipeBakeRequest(BaseModel):
    force: bool = False
    source_path: str | None = Field(
        default=None,
        description="Переопределение пути к инстансу лаунчера (Prism и т.д.)",
    )


class RecipeBakeResponse(BaseModel):
    version: str
    profile_id: str
    status: str
    recipe_count: int = 0
    item_count: int = 0
    duration_seconds: float | None = None
    log_tail: str | None = None
    error: str | None = None
    kept_previous_snapshot: bool = False
    backend_log_path: str | None = None
    bake_log_path: str | None = None


class RecipeStatsResponse(BaseModel):
    version: str
    profile_id: str
    has_stats: bool
    recipe_count: int = 0
    item_count: int = 0
    source: str = "none"  # snapshot | catalog | none


class AssetTaskProgress(BaseModel):
    running: bool = False
    done: int = 0
    total: int = 0
    error: str | None = None


class AssetRenderProgressResponse(BaseModel):
    version: str
    profile_id: str
    running: bool = False
    icons: AssetTaskProgress
    blocks: AssetTaskProgress


class AssetRenderStartResponse(BaseModel):
    version: str
    profile_id: str
    started: bool
