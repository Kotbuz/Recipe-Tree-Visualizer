from __future__ import annotations

from dataclasses import dataclass

from app.mod_deps.catalog import DependencyCatalogEntry
from app.mod_deps.curseforge import CurseForgeClient, ResolvedModFile
from app.mod_deps.modrinth import ModrinthClient


@dataclass(frozen=True)
class DependencyResolution:
    dependency_name: str
    resolved: ResolvedModFile | None
    manual_url: str | None
    error: str | None = None


class ModDependencyResolver:
    def __init__(
        self,
        *,
        modrinth: ModrinthClient,
        curseforge: CurseForgeClient,
    ) -> None:
        self._modrinth = modrinth
        self._curseforge = curseforge

    def resolve(
        self,
        *,
        entry: DependencyCatalogEntry,
        game_version: str,
    ) -> DependencyResolution:
        manual_url = _manual_url(entry)
        error: str | None = None

        try:
            modrinth_file = self._modrinth.resolve_forge_file(
                slug=entry.modrinth_slug,
                search_terms=entry.search_terms or (entry.dependency_name,),
                game_version=game_version,
            )
            if modrinth_file is not None:
                return DependencyResolution(
                    dependency_name=entry.dependency_name,
                    resolved=modrinth_file,
                    manual_url=modrinth_file.project_url or manual_url,
                )
        except Exception as exc:
            error = f"Modrinth: {exc}"

        if not self._curseforge.configured:
            return DependencyResolution(
                dependency_name=entry.dependency_name,
                resolved=None,
                manual_url=manual_url,
                error=error or "CurseForge API key is not configured",
            )

        try:
            curseforge_file = self._curseforge.resolve_forge_file(
                entry=entry,
                game_version=game_version,
            )
            if curseforge_file is not None:
                return DependencyResolution(
                    dependency_name=entry.dependency_name,
                    resolved=curseforge_file,
                    manual_url=curseforge_file.project_url or manual_url,
                )
            error = (error + "; " if error else "") + "CurseForge: no matching file"
        except Exception as exc:
            error = (error + "; " if error else "") + f"CurseForge: {exc}"

        return DependencyResolution(
            dependency_name=entry.dependency_name,
            resolved=None,
            manual_url=manual_url,
            error=error or "No matching mod file found",
        )


def _manual_url(entry: DependencyCatalogEntry) -> str | None:
    if entry.curseforge_slug:
        return f"https://www.curseforge.com/minecraft/mc-mods/{entry.curseforge_slug}/files/all"
    if entry.modrinth_slug:
        return f"https://modrinth.com/mod/{entry.modrinth_slug}/versions"
    return None
