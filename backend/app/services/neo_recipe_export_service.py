from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version
from app.services.host_paths import (
    host_path_unavailable_hint,
    map_windows_path_to_container,
    resolve_host_filesystem_path,
)
from app.services.modpack_version_detector import (
    detect_modpack_version_from_directory,
    find_modpack_metadata_root,
)
from app.services.profile_storage import read_profile_meta
from app.services.recipe_snapshot_service import (
    SNAPSHOT_FORMAT_VERSION,
    append_bake_log,
    bake_log_path,
    commit_snapshot,
    read_snapshot_status,
    record_bake_failure,
    recipes_snapshot_path,
)
from app.services.version_service import version_service


class NeoRecipeExportError(RuntimeError):
    pass


class NeoRecipeExportService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def get_status(self, version: str, profile_id: str) -> dict[str, Any]:
        status = read_snapshot_status(version, profile_id)
        meta = status.meta
        return {
            "has_snapshot": status.has_snapshot,
            "recipe_count": status.recipe_count,
            "exported_at": meta.exported_at if meta else None,
            "minecraft_version": meta.minecraft_version if meta else None,
            "loader_version": meta.loader_version if meta else None,
            "last_error": status.last_error,
        }

    def bake_profile(
        self,
        version: str,
        profile_id: str,
        *,
        force: bool = False,
        source_path_override: str | None = None,
    ) -> dict[str, Any]:
        profile_dir = version_service.profile_dir(version, profile_id)
        if not profile_dir.is_dir():
            raise NeoRecipeExportError(f"Профиль не найден: {profile_id}")

        meta = read_profile_meta(profile_dir)
        mc_version = self._resolve_minecraft_version(version, meta)
        if recipe_layout_for_version(mc_version) == "jvm":
            raise NeoRecipeExportError(
                f"Для Minecraft {mc_version} используйте JVM exporter (1.7.10). "
                "NeoForge in-game export пока только для data-layout (1.16+)."
            )

        loader = meta.get("loader") if isinstance(meta.get("loader"), str) else None
        loader_version = (
            meta.get("forge_version") if isinstance(meta.get("forge_version"), str) else None
        )
        if loader and loader.lower() not in {"neoforge", "forge"}:
            logger.warning("Profile loader is {}, continuing with NeoForge export", loader)

        instance_path_raw = (source_path_override or meta.get("source_path") or "").strip()
        if not instance_path_raw:
            raise NeoRecipeExportError(
                "Путь к инстансу лаунчера не задан. Импортируйте профиль из папки инстанса "
                "или укажите путь при сборке."
            )

        hint = host_path_unavailable_hint(instance_path_raw)
        if hint:
            raise NeoRecipeExportError(hint)

        instance_path = resolve_host_filesystem_path(instance_path_raw)
        if not instance_path.is_dir():
            raise NeoRecipeExportError(f"Папка инстанса не найдена: {instance_path_raw}")

        detected = detect_modpack_version_from_directory(instance_path)
        if detected is not None and detected.minecraft_version != mc_version:
            raise NeoRecipeExportError(
                f"Версия инстанса ({detected.minecraft_version}) не совпадает с профилем ({mc_version})"
            )
        if detected is not None:
            if detected.loader:
                loader = detected.loader
            if detected.forge_version:
                loader_version = detected.forge_version

        if not loader_version:
            raise NeoRecipeExportError(
                "Не удалось определить версию NeoForge. Убедитесь, что это Prism/CF инстанс "
                "с mmc-pack.json или minecraftinstance.json."
            )

        exporter_url = self._settings.neo_recipe_exporter_url.strip()
        if not exporter_url:
            raise NeoRecipeExportError(
                "NEO_RECIPE_EXPORTER_URL не задан. Запустите сервис recipe-exporter-neo "
                "(docker compose --profile neo-recipes up)."
            )

        output_dir = recipes_snapshot_path(version, profile_id).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        had_snapshot = read_snapshot_status(version, profile_id).has_snapshot
        payload = {
            "minecraft_version": mc_version,
            "loader_version": loader_version,
            "instance_path": self._path_for_exporter(instance_path_raw, instance_path),
            "output_dir": str(output_dir.resolve()),
            "storage_version": version,
            "profile_id": profile_id,
            "force": force,
        }

        started = datetime.now(UTC)
        try:
            result = self._call_exporter(exporter_url, payload)
        except NeoRecipeExportError as exc:
            record_bake_failure(version, profile_id, error=str(exc))
            return {
                "status": "error",
                "recipe_count": read_snapshot_status(version, profile_id).recipe_count,
                "duration_seconds": (datetime.now(UTC) - started).total_seconds(),
                "error": str(exc),
                "kept_previous_snapshot": had_snapshot,
                "log_tail": self._read_log_tail(version, profile_id),
            }

        if result.get("status") != "ok":
            error = str(result.get("error", "export failed"))
            log_tail = result.get("log_tail") or result.get("stderr_tail")
            record_bake_failure(version, profile_id, error=error, log_tail=log_tail)
            return {
                "status": "error",
                "recipe_count": read_snapshot_status(version, profile_id).recipe_count,
                "duration_seconds": result.get("duration_seconds"),
                "error": error,
                "kept_previous_snapshot": had_snapshot,
                "log_tail": log_tail,
            }

        snapshot_file = output_dir / "recipes.baked.json"
        if not snapshot_file.is_file():
            error = "Exporter завершился без recipes.baked.json"
            record_bake_failure(version, profile_id, error=error, log_tail=result.get("log_tail"))
            return {
                "status": "error",
                "recipe_count": read_snapshot_status(version, profile_id).recipe_count,
                "error": error,
                "kept_previous_snapshot": had_snapshot,
            }

        snapshot_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        if not isinstance(snapshot_payload, dict):
            raise NeoRecipeExportError("Некорректный recipes.baked.json от exporter")

        recipes_obj = snapshot_payload.get("recipes")
        recipe_count = (
            len(recipes_obj) if isinstance(recipes_obj, dict) else int(result.get("recipe_count", 0))
        )

        bake_meta = {
            "format_version": SNAPSHOT_FORMAT_VERSION,
            "minecraft_version": mc_version,
            "loader": loader or "neoforge",
            "loader_version": loader_version,
            "exported_at": datetime.now(UTC).isoformat(),
            "recipe_count": recipe_count,
            "instance_path": instance_path_raw,
        }
        commit_snapshot(
            version,
            profile_id,
            snapshot_payload=snapshot_payload,
            meta=bake_meta,
            log_text=result.get("log_tail"),
        )

        from app.recipes.manager import recipe_manager

        recipe_manager.clear_version_cache(version, profile_id=profile_id)
        from app.services.recipe_snapshot_service import clear_snapshot_cache

        clear_snapshot_cache()

        return {
            "status": "ok",
            "recipe_count": recipe_count,
            "duration_seconds": result.get("duration_seconds"),
            "log_tail": result.get("log_tail"),
            "kept_previous_snapshot": False,
        }

    def _call_exporter(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = base_url.rstrip("/") + "/export"
        timeout = httpx.Timeout(self._settings.neo_recipe_exporter_timeout_seconds)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise NeoRecipeExportError(f"Neo recipe exporter недоступен: {exc}") from exc

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise NeoRecipeExportError(
                f"Neo exporter вернул не-JSON ({response.status_code})"
            ) from exc

        if response.status_code >= 400 and isinstance(body, dict):
            raise NeoRecipeExportError(str(body.get("error", body)))
        if not isinstance(body, dict):
            raise NeoRecipeExportError("Neo exporter returned invalid payload")
        return body

    def _resolve_minecraft_version(self, storage_version: str, meta: dict[str, Any]) -> str:
        raw = meta.get("minecraft_version")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return storage_version

    def _path_for_exporter(self, raw: str, resolved: Path) -> str:
        from pathlib import PureWindowsPath

        if raw.strip() and map_windows_path_to_container(PureWindowsPath(raw.strip())):
            return str(resolved.resolve())
        return str(resolved.resolve())

    def _read_log_tail(self, version: str, profile_id: str) -> str | None:
        path = bake_log_path(version, profile_id)
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-8000:] if text else None


neo_recipe_export_service = NeoRecipeExportService()
