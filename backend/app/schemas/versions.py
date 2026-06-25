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
