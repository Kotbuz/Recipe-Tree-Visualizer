from pydantic import BaseModel


class VersionListResponse(BaseModel):
    versions: list[str]


class VersionCatalogEntryResponse(BaseModel):
    version: str
    installed: bool


class VersionCatalogResponse(BaseModel):
    releases: list[VersionCatalogEntryResponse]


class VersionInstallResponse(BaseModel):
    version: str
    client_jar_path: str
    icons_rendered: int
    icon_errors: list[str]


class ItemIconManifestResponse(BaseModel):
    version: str
    icons: list[str]
    revision: str = "0"


class IngredientIndexResponse(BaseModel):
    version: str
    tags: dict[str, list[str]]
    aliases: dict[str, str]


class ModDependencyIssueResponse(BaseModel):
    mod_id: str
    jar_name: str
    requires: list[str]


class RecipeExportStatusResponse(BaseModel):
    version: str
    layout: str
    exported_recipe_count: int
    installed_mod_jars: list[str]
    recipe_mod_ids: list[str]
    mods_without_recipes: list[str]
    missing_dependencies: list[ModDependencyIssueResponse]
    warnings: list[str]
    log_errors: list[str] = []
