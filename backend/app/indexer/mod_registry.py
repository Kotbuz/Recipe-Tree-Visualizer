from app.schemas.domain import ModSummary


class ModRegistry:
    def __init__(self) -> None:
        self._mods: dict[str, ModSummary] = {}

    def list_mods(self) -> list[ModSummary]:
        return list(self._mods.values())

    def register_summary(self, summary: ModSummary) -> ModSummary:
        self._mods[summary.mod_id] = summary
        return summary

    def clear(self) -> None:
        self._mods.clear()


registry = ModRegistry()
