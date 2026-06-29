from pydantic import BaseModel


class DependencyDownloadResultResponse(BaseModel):
    dependency: str
    status: str
    jar_name: str | None = None
    source: str | None = None
    manual_url: str | None = None
    error: str | None = None


class ModDependencyDownloadResponse(BaseModel):
    version: str
    requested: list[str]
    results: list[DependencyDownloadResultResponse]
    all_resolved: bool
    export_triggered: bool
    export_recipe_count: int | None = None
    export_error: str | None = None
