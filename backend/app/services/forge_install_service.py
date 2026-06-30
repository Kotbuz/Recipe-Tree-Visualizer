from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from app.services import java_runtime_service
from app.services.modpack_version_detector import forge_installer_version

_LEGACY_FORGE_VERSION = "1.7.10-10.13.4.1448-1.7.10"
_DEFAULT_LIBRARY_REPO = "https://libraries.minecraft.net/"

_HTTP_HEADERS = {"User-Agent": "Recipe-Tree-Visualizer/1.0"}
_HTTP_TIMEOUT = httpx.Timeout(120.0, connect=30.0)
_HTTP_RETRIES = 3


def _uses_legacy_forge_install(minecraft_version: str) -> bool:
    return minecraft_version.startswith("1.7")


def _supports_modern_forge_install(minecraft_version: str) -> bool:
    parts = minecraft_version.split(".")
    try:
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        return False
    return minor > 21 or (minor == 21 and patch >= 0)


def _required_java_major(minecraft_version: str) -> int:
    parts = minecraft_version.split(".")
    try:
        minor = int(parts[1])
    except (IndexError, ValueError):
        return 21
    if minor >= 21:
        return 21
    if minor >= 17:
        return 17
    return 8


@dataclass(frozen=True)
class _ForgeInstallLibrary:
    name: str
    group: str
    artifact: str
    version: str
    rel_dir: str
    jar_name: str
    url: str
    checksums: tuple[str, ...]


def _parse_maven_name(name: str) -> tuple[str, str, str]:
    parts = name.split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid Maven coordinate: {name}")
    return parts[0], parts[1], parts[2]


def _library_rel_dir(group: str, artifact: str, version: str) -> str:
    return f"{group.replace('.', '/')}/{artifact}/{version}"


def _library_jar_name(artifact: str, version: str) -> str:
    return f"{artifact}-{version}.jar"


def _library_download_url(
    entry: dict[str, object],
    group: str,
    artifact: str,
    version: str,
) -> str:
    base = str(entry.get("url") or _DEFAULT_LIBRARY_REPO)
    if not base.endswith("/"):
        base += "/"
    rel = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.jar"
    return base + rel


def _sha1_hex(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest().lower()


def _library_content_valid(content: bytes, checksums: tuple[str, ...]) -> bool:
    if len(content) < 128 or content[:4] != b"PK\x03\x04":
        return False
    if not checksums:
        return True
    digest = _sha1_hex(content)
    return any(digest == checksum.lower() for checksum in checksums)


def _read_server_libraries(installer_path: Path) -> tuple[_ForgeInstallLibrary, ...]:
    with zipfile.ZipFile(installer_path) as archive:
        profile = json.loads(archive.read("install_profile.json"))
    libraries: list[_ForgeInstallLibrary] = []
    for entry in profile["versionInfo"]["libraries"]:
        if not entry.get("serverreq"):
            continue
        group, artifact, version = _parse_maven_name(str(entry["name"]))
        if group == "net.minecraftforge":
            continue
        rel_dir = _library_rel_dir(group, artifact, version)
        jar_name = _library_jar_name(artifact, version)
        checksums = tuple(str(value) for value in entry.get("checksums") or ())
        libraries.append(
            _ForgeInstallLibrary(
                name=str(entry["name"]),
                group=group,
                artifact=artifact,
                version=version,
                rel_dir=rel_dir,
                jar_name=jar_name,
                url=_library_download_url(entry, group, artifact, version),
                checksums=checksums,
            )
        )
    return tuple(libraries)


class ForgeInstallError(RuntimeError):
    pass


@dataclass
class ForgeInstallStatus:
    minecraft_version: str
    forge_build: str
    installed: bool
    running: bool
    phase: str
    message: str
    progress: int
    error: str | None = None


def _state_key(minecraft_version: str, forge_build: str) -> str:
    return f"{minecraft_version}::{forge_build}"


class ForgeInstallService:
    def __init__(self) -> None:
        self._states: dict[str, ForgeInstallStatus] = {}
        self._guard = threading.Lock()

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def universal_forge_dir(
        self,
        minecraft_version: str,
        *,
        forge_build: str | None = None,
    ) -> Path:
        base = self._repo_root() / "recipe-exporter" / "forge-runtime" / minecraft_version
        if forge_build:
            return base / forge_build
        return base

    def find_universal_forge_jar(self, forge_dir: Path) -> Path | None:
        jars = sorted(forge_dir.glob("forge-*-universal.jar"))
        return jars[0] if jars else None

    def find_forge_server_jar(self, forge_dir: Path, forge_version: str) -> Path | None:
        direct = (
            forge_dir
            / "libraries"
            / "net"
            / "minecraftforge"
            / "forge"
            / forge_version
            / f"forge-{forge_version}-server.jar"
        )
        if direct.is_file():
            return direct
        jars = sorted(forge_dir.glob("**/forge-*-server.jar"))
        return jars[0] if jars else None

    def is_installed(self, minecraft_version: str, forge_build: str) -> bool:
        forge_dir = self.universal_forge_dir(minecraft_version, forge_build=forge_build)
        if self.find_universal_forge_jar(forge_dir) is not None:
            return True
        if _uses_legacy_forge_install(minecraft_version):
            return False
        forge_version = forge_installer_version(minecraft_version, forge_build)
        return self.find_forge_server_jar(forge_dir, forge_version) is not None

    def get_status(self, minecraft_version: str, forge_build: str) -> ForgeInstallStatus:
        key = _state_key(minecraft_version, forge_build)
        with self._guard:
            state = self._states.get(key)
            if state is not None:
                return state
        installed = self.is_installed(minecraft_version, forge_build)
        return ForgeInstallStatus(
            minecraft_version=minecraft_version,
            forge_build=forge_build,
            installed=installed,
            running=False,
            phase="ready" if installed else "idle",
            message="Forge уже установлен" if installed else "Ожидание установки",
            progress=100 if installed else 0,
        )

    def prepare(self, minecraft_version: str, forge_build: str) -> ForgeInstallStatus:
        if not (
            _uses_legacy_forge_install(minecraft_version)
            or _supports_modern_forge_install(minecraft_version)
        ):
            raise ForgeInstallError(
                "Автоустановка Forge поддерживается для 1.7.x и 1.21+ "
                f"(получено {minecraft_version})"
            )
        if self.is_installed(minecraft_version, forge_build):
            status = ForgeInstallStatus(
                minecraft_version=minecraft_version,
                forge_build=forge_build,
                installed=True,
                running=False,
                phase="done",
                message="Forge уже установлен",
                progress=100,
            )
            with self._guard:
                self._states[_state_key(minecraft_version, forge_build)] = status
            return status

        key = _state_key(minecraft_version, forge_build)
        with self._guard:
            existing = self._states.get(key)
            if existing is not None and existing.running:
                return existing
            status = ForgeInstallStatus(
                minecraft_version=minecraft_version,
                forge_build=forge_build,
                installed=False,
                running=True,
                phase="starting",
                message="Подготовка установки Forge…",
                progress=1,
            )
            self._states[key] = status
            thread = threading.Thread(
                target=self._run_install,
                args=(minecraft_version, forge_build),
                daemon=True,
                name=f"forge-install-{forge_build}",
            )
            thread.start()
            return status

    def ensure_installed(
        self,
        minecraft_version: str,
        *,
        forge_build: str | None = None,
    ) -> Path:
        forge_dir = self.universal_forge_dir(minecraft_version, forge_build=forge_build)
        forge_dir.mkdir(parents=True, exist_ok=True)

        existing = self.find_universal_forge_jar(forge_dir)
        if existing is not None:
            return existing

        if forge_build:
            self._install_sync(minecraft_version, forge_build)
            universal = self.find_universal_forge_jar(forge_dir)
            if universal is None:
                raise ForgeInstallError(
                    f"Forge universal jar not found after install in {forge_dir}"
                )
            return universal

        return self._install_legacy(minecraft_version, forge_dir)

    def _install_legacy(self, minecraft_version: str, forge_dir: Path) -> Path:
        forge_version = _LEGACY_FORGE_VERSION
        self._download_and_install(
            minecraft_version,
            forge_build=None,
            forge_dir=forge_dir,
            forge_version=forge_version,
            on_progress=None,
        )
        universal = self.find_universal_forge_jar(forge_dir)
        if universal is None:
            raise ForgeInstallError(f"Forge universal jar not found after install in {forge_dir}")
        return universal

    def _run_install(self, minecraft_version: str, forge_build: str) -> None:
        key = _state_key(minecraft_version, forge_build)
        try:
            self._install_sync(minecraft_version, forge_build)
            status = ForgeInstallStatus(
                minecraft_version=minecraft_version,
                forge_build=forge_build,
                installed=True,
                running=False,
                phase="done",
                message="Forge установлен",
                progress=100,
            )
            with self._guard:
                self._states[key] = status
        except Exception as exc:
            logger.exception(
                "Forge install failed for {} {}",
                minecraft_version,
                forge_build,
            )
            status = ForgeInstallStatus(
                minecraft_version=minecraft_version,
                forge_build=forge_build,
                installed=False,
                running=False,
                phase="error",
                message="Не удалось установить Forge",
                progress=0,
                error=str(exc),
            )
            with self._guard:
                self._states[key] = status

    def _install_sync(self, minecraft_version: str, forge_build: str) -> None:
        forge_dir = self.universal_forge_dir(minecraft_version, forge_build=forge_build)
        forge_dir.mkdir(parents=True, exist_ok=True)
        if self.is_installed(minecraft_version, forge_build):
            return

        forge_version = forge_installer_version(minecraft_version, forge_build)
        self._download_and_install(
            minecraft_version,
            forge_build=forge_build,
            forge_dir=forge_dir,
            forge_version=forge_version,
            on_progress=lambda phase, message, progress: self._update_state(
                minecraft_version, forge_build, phase, message, progress
            ),
        )

    def _update_state(
        self,
        minecraft_version: str,
        forge_build: str,
        phase: str,
        message: str,
        progress: int,
    ) -> None:
        key = _state_key(minecraft_version, forge_build)
        with self._guard:
            self._states[key] = ForgeInstallStatus(
                minecraft_version=minecraft_version,
                forge_build=forge_build,
                installed=False,
                running=True,
                phase=phase,
                message=message,
                progress=max(0, min(100, progress)),
            )

    def _download_and_install(
        self,
        minecraft_version: str,
        *,
        forge_build: str | None,
        forge_dir: Path,
        forge_version: str,
        on_progress: Callable[[str, str, int], None] | None,
    ) -> None:
        def report(phase: str, message: str, progress: int) -> None:
            if on_progress is not None:
                on_progress(phase, message, progress)

        report("downloading_installer", f"Скачивание Forge {forge_version}…", 5)
        installer_name = f"forge-{forge_version}-installer.jar"
        installer_path = forge_dir / installer_name
        installer_url = (
            "https://maven.minecraftforge.net/net/minecraftforge/forge/"
            f"{forge_version}/{installer_name}"
        )
        legacy_install = _uses_legacy_forge_install(minecraft_version)
        with httpx.Client(follow_redirects=True, timeout=_HTTP_TIMEOUT) as client:
            response = self._http_get_with_retries(
                client,
                installer_url,
                headers=_HTTP_HEADERS,
            )
            installer_path.write_bytes(response.content)
            report("downloading_installer", "Установщик Forge скачан", 25)
            if legacy_install:
                self._bootstrap_forge_installer_libraries(
                    forge_dir,
                    installer_path,
                    client,
                    report,
                )

        report(
            "running_installer", "Запуск установщика Forge (это может занять несколько минут)…", 50
        )
        try:
            subprocess.run(
                [
                    self._resolve_java_executable(minecraft_version),
                    "-jar",
                    str(installer_path),
                    "--installServer",
                ],
                check=True,
                cwd=forge_dir,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            artifact = "universal server" if legacy_install else "server"
            raise ForgeInstallError(
                f"Не удалось установить Forge {artifact} ({forge_version}). {detail}"
            ) from exc
        finally:
            installer_path.unlink(missing_ok=True)

        report("finalizing", "Завершение установки Forge…", 95)
        (forge_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        if legacy_install:
            universal = self.find_universal_forge_jar(forge_dir)
            if universal is None:
                raise ForgeInstallError(
                    f"Forge universal jar not found after install in {forge_dir}"
                )
            installed_artifact = universal
        else:
            server = self.find_forge_server_jar(forge_dir, forge_version)
            if server is None:
                raise ForgeInstallError(f"Forge server jar not found after install in {forge_dir}")
            installed_artifact = server
        logger.info(
            "Forge {} installed for Minecraft {} at {}",
            forge_version,
            minecraft_version,
            installed_artifact,
        )

    def _http_get_with_retries(
        self,
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, _HTTP_RETRIES + 1):
            try:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt >= _HTTP_RETRIES:
                    break
                logger.warning(
                    "Forge download attempt {}/{} failed for {}: {}",
                    attempt,
                    _HTTP_RETRIES,
                    url,
                    exc,
                )
                time.sleep(2 * attempt)
        assert last_error is not None
        raise ForgeInstallError(
            f"Не удалось скачать {url} после {_HTTP_RETRIES} попыток: {last_error}"
        ) from last_error

    def _write_bootstrap_jar(
        self,
        libraries_dir: Path,
        rel_dir: str,
        jar_name: str,
        content: bytes,
    ) -> Path:
        destination = libraries_dir / rel_dir / jar_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def _bootstrap_forge_installer_libraries(
        self,
        forge_dir: Path,
        installer_path: Path,
        client: httpx.Client,
        report: Callable[[str, str, int], None],
    ) -> None:
        libraries_dir = forge_dir / "libraries"
        libraries = _read_server_libraries(installer_path)
        total = len(libraries)
        for index, library in enumerate(libraries, start=1):
            destination = libraries_dir / library.rel_dir / library.jar_name
            if destination.is_file():
                existing = destination.read_bytes()
                if _library_content_valid(existing, library.checksums):
                    continue

            report(
                "downloading_libraries",
                f"Библиотеки Forge ({index}/{total}): {library.artifact}",
                25 + int(20 * index / total),
            )
            response = self._http_get_with_retries(
                client,
                library.url,
                headers=_HTTP_HEADERS,
            )
            content = response.content
            if not _library_content_valid(content, library.checksums):
                raise ForgeInstallError(
                    "Неверная контрольная сумма библиотеки Forge "
                    f"{library.name} (ожидался SHA1 из install_profile.json)."
                )
            self._write_bootstrap_jar(
                libraries_dir,
                library.rel_dir,
                library.jar_name,
                content,
            )

        missing = [
            str(libraries_dir / library.rel_dir / library.jar_name)
            for library in libraries
            if not (libraries_dir / library.rel_dir / library.jar_name).is_file()
        ]
        if missing:
            raise ForgeInstallError(
                "Не удалось подготовить библиотеки Forge перед установкой: " + ", ".join(missing)
            )

    def _resolve_java_executable(self, minecraft_version: str) -> str:
        required_major = _required_java_major(minecraft_version)
        try:
            return java_runtime_service.resolve_java_executable(required_major)
        except FileNotFoundError as exc:
            raise ForgeInstallError(str(exc)) from exc


forge_install_service = ForgeInstallService()
