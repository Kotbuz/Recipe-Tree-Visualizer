from pydantic import BaseModel


class VersionListResponse(BaseModel):
    versions: list[str]


class ItemIconManifestResponse(BaseModel):
    version: str
    icons: list[str]
