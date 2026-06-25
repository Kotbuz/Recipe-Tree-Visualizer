from pydantic import BaseModel


class VersionListResponse(BaseModel):
    versions: list[str]


class ItemIconManifestResponse(BaseModel):
    version: str
    icons: list[str]
    revision: str = "0"


class IngredientIndexResponse(BaseModel):
    version: str
    tags: dict[str, list[str]]
    aliases: dict[str, str]
