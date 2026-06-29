from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ResolvedModFile:
    file_name: str
    download_url: str
    source: str
    project_url: str | None = None


class ModrinthClient:
    BASE_URL = "https://api.modrinth.com/v2"

    def __init__(self, *, timeout: float, user_agent: str) -> None:
        self._timeout = timeout
        self._headers = {"User-Agent": user_agent}

    def resolve_forge_file(
        self,
        *,
        slug: str | None,
        search_terms: tuple[str, ...],
        game_version: str,
    ) -> ResolvedModFile | None:
        project_id = self._resolve_project_id(slug, search_terms)
        if project_id is None:
            return None

        versions = self._get_versions(project_id, game_version)
        if not versions:
            return None

        for version_payload in versions:
            files = version_payload.get("files")
            if not isinstance(files, list):
                continue
            for file_payload in files:
                if not isinstance(file_payload, dict):
                    continue
                url = file_payload.get("url")
                filename = file_payload.get("filename")
                if isinstance(url, str) and isinstance(filename, str) and filename.endswith(".jar"):
                    project_url = f"https://modrinth.com/mod/{slug or project_id}"
                    return ResolvedModFile(
                        file_name=filename,
                        download_url=url,
                        source="modrinth",
                        project_url=project_url,
                    )
        return None

    def _resolve_project_id(
        self,
        slug: str | None,
        search_terms: tuple[str, ...],
    ) -> str | None:
        if slug:
            project = self._get_json(f"/project/{slug}")
            if isinstance(project, dict) and isinstance(project.get("id"), str):
                return project["id"]

        for term in search_terms:
            hits = self._search(term)
            if hits:
                return hits[0]
        return None

    def _search(self, query: str) -> list[str]:
        payload = self._get_json(
            "/search",
            params={
                "query": query,
                "limit": 5,
                "facets": '[["project_type:mod"]]',
            },
        )
        if not isinstance(payload, dict):
            return []
        hits = payload.get("hits")
        if not isinstance(hits, list):
            return []
        ids: list[str] = []
        for hit in hits:
            if isinstance(hit, dict) and isinstance(hit.get("project_id"), str):
                ids.append(hit["project_id"])
        return ids

    def _get_versions(self, project_id: str, game_version: str) -> list[dict[str, object]]:
        payload = self._get_json(
            f"/project/{project_id}/version",
            params={
                "loaders": '["forge"]',
                "game_versions": f'["{game_version}"]',
            },
        )
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _get_json(self, path: str, *, params: dict[str, str] | None = None) -> object:
        with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
            response = client.get(f"{self.BASE_URL}{path}", params=params)
            response.raise_for_status()
            return response.json()
