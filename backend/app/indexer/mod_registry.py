from app.schemas.domain import ModSummary
from app.services.profile_storage import DEFAULT_PROFILE_ID, profile_storage_key


class ModRegistry:
    def __init__(self) -> None:
        self._mods_by_version: dict[str, dict[str, ModSummary]] = {}

    def list_mods(self, version: str) -> list[ModSummary]:
        bucket = self._mods_by_version.get(version)
        if bucket is None and "::" not in version:
            bucket = self._mods_by_version.get(profile_storage_key(version, DEFAULT_PROFILE_ID))
        return list((bucket or {}).values())

    def register_summary(self, version: str, summary: ModSummary) -> ModSummary:
        bucket = self._mods_by_version.setdefault(version, {})
        bucket[summary.mod_id] = summary
        return summary

    def clear(self) -> None:
        self._mods_by_version.clear()

    def clear_version(self, version: str) -> None:
        self._mods_by_version.pop(version, None)
        if "::" not in version:
            self._mods_by_version.pop(profile_storage_key(version, DEFAULT_PROFILE_ID), None)


registry = ModRegistry()
