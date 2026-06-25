from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path, PurePosixPath

TAG_PATH = re.compile(r"^data/([^/]+)/tags/(?:item|items)/(.+\.json)$")


def normalize_tag_id(raw: str) -> str:
    cleaned = raw.strip().removeprefix("#")
    if cleaned.startswith("tag:"):
        return cleaned
    return f"tag:{cleaned}"


def is_tag_id(value: str) -> bool:
    return value.startswith("tag:") or value.startswith("#")


class TagLoader:
    def load_from_jar(self, jar_path: Path) -> dict[str, frozenset[str]]:
        tags: dict[str, set[str]] = {}
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.namelist():
                    match = TAG_PATH.match(entry)
                    if not match:
                        continue
                    namespace, relative_path = match.groups()
                    tag_name = PurePosixPath(relative_path).stem
                    tag_id = normalize_tag_id(f"{namespace}:{tag_name}")
                    try:
                        payload = json.loads(archive.read(entry))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    members = self._parse_values(payload.get("values"))
                    if members:
                        tags.setdefault(tag_id, set()).update(members)
        except (OSError, zipfile.BadZipFile):
            return {}
        return {tag_id: frozenset(members) for tag_id, members in tags.items()}

    def merge_tag_maps(self, *maps: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
        merged: dict[str, set[str]] = {}
        for tag_map in maps:
            for tag_id, members in tag_map.items():
                merged.setdefault(normalize_tag_id(tag_id), set()).update(members)
        return {tag_id: frozenset(members) for tag_id, members in merged.items()}

    def resolve_transitive(
        self,
        tag_map: dict[str, frozenset[str]],
        tag_id: str,
        *,
        _visited: frozenset[str] | None = None,
    ) -> frozenset[str]:
        normalized = normalize_tag_id(tag_id)
        visited = _visited or frozenset()
        if normalized in visited:
            return frozenset()

        direct = tag_map.get(normalized, frozenset())
        resolved: set[str] = set()
        for member in direct:
            if is_tag_id(member) or member.startswith("#"):
                nested = self.resolve_transitive(
                    tag_map,
                    member,
                    _visited=visited | {normalized},
                )
                resolved.update(nested)
            else:
                resolved.add(member)
        return frozenset(resolved)

    def _parse_values(self, values: object) -> set[str]:
        if not isinstance(values, list):
            return set()

        members: set[str] = set()
        for value in values:
            if isinstance(value, str):
                members.add(value)
                continue
            if isinstance(value, dict):
                entry_id = value.get("id")
                if isinstance(entry_id, str):
                    members.add(entry_id)
        return members
