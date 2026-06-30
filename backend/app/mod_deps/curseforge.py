from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.mod_deps.catalog import DependencyCatalogEntry

_CURSEFORGE_MINECRAFT_GAME_ID = 432
_RELEASE_TYPES = {1: 0, 2: 1, 3: 2}  # prefer Release, then Beta, then Alpha


@dataclass(frozen=True)
class ResolvedModFile:
    file_name: str
    download_url: str
    source: str
    project_url: str | None = None


class CurseForgeClient:
    BASE_URL = "https://api.curseforge.com/v1"

    def __init__(self, *, api_key: str, user_agent: str, timeout: float) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._headers = {
            "x-api-key": self._api_key,
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def resolve_forge_file(
        self,
        *,
        entry: DependencyCatalogEntry,
        game_version: str,
    ) -> ResolvedModFile | None:
        if not self.configured:
            return None

        mod_id = entry.curseforge_project_id
        slug = entry.curseforge_slug
        if mod_id is None:
            mod_id = self._search_mod_id(entry.search_terms or (entry.dependency_name,))
            if mod_id is None:
                return None

        files = self._list_files(mod_id)
        selected = _pick_file(files, game_version, entry.file_name_contains)
        if selected is None:
            return None

        file_id = selected.get("id")
        file_name = selected.get("fileName")
        if not isinstance(file_id, int) or not isinstance(file_name, str):
            return None

        download_url = selected.get("downloadUrl")
        if not isinstance(download_url, str) or not download_url:
            download_url = self._fetch_download_url(mod_id, file_id)
        if not download_url:
            return None

        project_url = None
        if slug:
            project_url = f"https://www.curseforge.com/minecraft/mc-mods/{slug}"
        elif isinstance(selected.get("projectId"), int):
            project_url = (
                f"https://www.curseforge.com/minecraft/mc-mods/project/{selected['projectId']}"
            )

        return ResolvedModFile(
            file_name=file_name,
            download_url=download_url,
            source="curseforge",
            project_url=project_url,
        )

    def _search_mod_id(self, terms: tuple[str, ...]) -> int | None:
        for term in terms:
            payload = self._get_json(
                "/mods/search",
                params={
                    "gameId": str(_CURSEFORGE_MINECRAFT_GAME_ID),
                    "searchFilter": term,
                    "pageSize": "5",
                },
            )
            if not isinstance(payload, dict):
                continue
            data = payload.get("data")
            if not isinstance(data, list):
                continue
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("id"), int):
                    return item["id"]
        return None

    def _list_files(self, mod_id: int) -> list[dict[str, object]]:
        payload = self._get_json(f"/mods/{mod_id}/files", params={"pageSize": "50"})
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _fetch_download_url(self, mod_id: int, file_id: int) -> str | None:
        payload = self._get_json(f"/mods/{mod_id}/files/{file_id}/download-url")
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        return data if isinstance(data, str) else None

    def _get_json(self, path: str, *, params: dict[str, str] | None = None) -> object:
        with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
            response = client.get(f"{self.BASE_URL}{path}", params=params)
            response.raise_for_status()
            return response.json()


def _pick_file(
    files: list[dict[str, object]],
    game_version: str,
    name_contains: tuple[str, ...],
) -> dict[str, object] | None:
    candidates: list[dict[str, object]] = []
    for file_payload in files:
        game_versions = file_payload.get("gameVersions")
        file_name = file_payload.get("fileName")
        if not isinstance(game_versions, list) or not isinstance(file_name, str):
            continue
        if game_version not in game_versions:
            continue
        if name_contains and not all(part.lower() in file_name.lower() for part in name_contains):
            continue
        candidates.append(file_payload)

    if not candidates:
        for file_payload in files:
            game_versions = file_payload.get("gameVersions")
            file_name = file_payload.get("fileName")
            if (
                isinstance(game_versions, list)
                and game_version in game_versions
                and isinstance(file_name, str)
                and file_name.endswith(".jar")
            ):
                candidates.append(file_payload)

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda item: (
            _RELEASE_TYPES.get(item.get("releaseType"), 99)
            if isinstance(item.get("releaseType"), int)
            else 99,
            str(item.get("fileDate") or ""),
        ),
    )[0]
