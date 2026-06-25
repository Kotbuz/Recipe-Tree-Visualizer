from app.schemas.domain import ModSummary


class ModRegistry:
    def __init__(self) -> None:
        self._mods_by_version: dict[str, dict[str, ModSummary]] = {}

    def list_mods(self, version: str) -> list[ModSummary]:
        return list(self._mods_by_version.get(version, {}).values())

    def register_summary(self, version: str, summary: ModSummary) -> ModSummary:
        bucket = self._mods_by_version.setdefault(version, {})
        bucket[summary.mod_id] = summary
        return summary

    def clear(self) -> None:
        self._mods_by_version.clear()

    def clear_version(self, version: str) -> None:
        self._mods_by_version.pop(version, None)


registry = ModRegistry()
