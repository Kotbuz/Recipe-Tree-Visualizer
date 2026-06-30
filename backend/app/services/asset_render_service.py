from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.services.block_texture_service import block_texture_service
from app.services.profile_storage import DEFAULT_PROFILE_ID
from app.services.profile_service import profile_service
from app.services.vanilla_icon_service import vanilla_icon_service
from app.services.version_service import version_service


@dataclass
class TaskProgress:
    running: bool = False
    done: int = 0
    total: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "done": self.done,
            "total": self.total,
            "error": self.error,
        }


@dataclass
class AssetRenderState:
    icons: TaskProgress = field(default_factory=TaskProgress)
    blocks: TaskProgress = field(default_factory=TaskProgress)

    @property
    def running(self) -> bool:
        return self.icons.running or self.blocks.running

    def as_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "icons": self.icons.as_dict(),
            "blocks": self.blocks.as_dict(),
        }


class AssetRenderService:
    """Фоновый рендер иконок и извлечение текстур блоков с прогрессом в памяти.

    Иконки и блоки идут последовательно (P3). Реестр прогресса — in-memory,
    бэкенд однопроцессный. Повторный запуск пока идёт текущий — отклоняется.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, AssetRenderState] = {}
        self._threads: dict[str, threading.Thread] = {}

    @staticmethod
    def _key(version: str, profile_id: str) -> str:
        return f"{version}::{profile_id}"

    def get_state(self, version: str, profile_id: str) -> AssetRenderState:
        with self._lock:
            return self._states.get(self._key(version, profile_id), AssetRenderState())

    def is_running(self, version: str, profile_id: str) -> bool:
        with self._lock:
            thread = self._threads.get(self._key(version, profile_id))
            return bool(thread and thread.is_alive())

    def has_gaps(self, version: str, profile_id: str | None = None) -> bool:
        """Есть ли пробелы в иконках или текстурах блоков активного профиля."""
        try:
            required = set(
                vanilla_icon_service.collect_required_icon_ids(version, profile_id=profile_id)
            )
            existing = version_service.list_rendered_icon_ids(version, profile_id=profile_id)
            if required - existing:
                return True
            block_types = block_texture_service.count_block_types(version, profile_id=profile_id)
            if block_types > 0:
                output_dir = version_service.profile_block_textures_dir(
                    version, profile_id, create=False
                )
                existing_blocks = len(list(output_dir.glob("*.png"))) if output_dir.is_dir() else 0
                if existing_blocks < block_types:
                    return True
        except Exception as exc:  # noqa: BLE001 - проверка пробелов не должна падать
            logger.warning("Asset gap check failed for {}::{}: {}", version, profile_id, exc)
        return False

    def can_render_for_profile(self, version: str, profile_id: str) -> bool:
        """Vanilla/default — без source_path; модпак — только с папкой инстанса (Z1)."""
        if profile_id == DEFAULT_PROFILE_ID:
            return True
        try:
            profile = profile_service.get_profile(version, profile_id)
        except Exception:
            return False
        return bool(profile.source_path and profile.source_path.strip())

    def maybe_start_if_gaps(self, version: str, profile_id: str) -> bool:
        """Догонка пробелов: старт фонового рендера, если разрешено и есть что доделать."""
        if not self.can_render_for_profile(version, profile_id):
            return False
        if self.is_running(version, profile_id):
            return False
        if not self.has_gaps(version, profile_id):
            return False
        return self.start(version, profile_id, full_rescan=False)

    def start(
        self,
        version: str,
        profile_id: str,
        *,
        full_rescan: bool = False,
    ) -> bool:
        """Запускает фоновый проход. Возвращает False, если он уже идёт."""
        key = self._key(version, profile_id)
        with self._lock:
            existing = self._threads.get(key)
            if existing and existing.is_alive():
                return False
            self._states[key] = AssetRenderState(
                icons=TaskProgress(running=True),
                blocks=TaskProgress(running=True),
            )
            thread = threading.Thread(
                target=self._run,
                args=(version, profile_id, full_rescan),
                name=f"asset-render-{profile_id}",
                daemon=True,
            )
            self._threads[key] = thread
            thread.start()
            return True

    def _run(self, version: str, profile_id: str, full_rescan: bool) -> None:
        state = self.get_state(version, profile_id)
        # 1. Иконки предметов.
        try:
            def icon_progress(done: int, total: int) -> None:
                state.icons.done = done
                state.icons.total = total

            result = vanilla_icon_service.ensure_icons(
                version,
                profile_id=profile_id,
                force=full_rescan,
                progress_cb=icon_progress,
            )
            if result.errors:
                state.icons.error = "; ".join(result.errors)
        except Exception as exc:  # noqa: BLE001 - фоновую задачу нельзя ронять
            logger.exception("Icon render failed for {}::{}", version, profile_id)
            state.icons.error = str(exc)
        finally:
            state.icons.running = False

        # 2. Текстуры блоков — запускаем всегда, даже если иконки упали (X1).
        try:
            def block_progress(done: int, total: int) -> None:
                state.blocks.done = done
                state.blocks.total = total

            block_result = block_texture_service.extract(
                version,
                profile_id=profile_id,
                force=full_rescan,
                progress_cb=block_progress,
            )
            if block_result.errors:
                state.blocks.error = "; ".join(block_result.errors)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Block texture extract failed for {}::{}", version, profile_id)
            state.blocks.error = str(exc)
        finally:
            state.blocks.running = False


asset_render_service = AssetRenderService()
