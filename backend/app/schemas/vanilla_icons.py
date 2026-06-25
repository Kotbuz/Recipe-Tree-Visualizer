from pydantic import BaseModel


class VanillaIconRenderResponse(BaseModel):
    version: str
    required: int
    already_present: int
    requested: int
    rendered: int
    skipped: int
    errors: list[str]
