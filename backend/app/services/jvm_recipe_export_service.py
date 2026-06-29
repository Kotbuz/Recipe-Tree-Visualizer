from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import glob
import threading
import time
import zipfile
from pathlib import Path

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version
from app.services.forge_install_service import ForgeInstallError, forge_install_service
from app.services.modpack_version_detector import forge_installer_version
from app.services.profile_storage import resolve_profile_forge_build
from app.services.version_service import version_service

_LEGACY_FORGE_VERSION = "1.7.10-10.13.4.1448-1.7.10"

# Не копируем в forge-runtime/mods: ломают DepLoader / не дают рецептов.
_FORGE_EXPORT_MOD_SKIP_FRAGMENTS = (
    "forgemicroblock",
    "commons-codec",
    "commons-compress",
    "commons-logging",
    "vorbis-java",
)

# Клиентские моды (UI, ресурспаки): падают на dedicated headless export.
_FORGE_EXPORT_CLIENT_ONLY_FRAGMENTS = (
    "resourceloader",
    "additionalresources",
    "custommainmenu",
    "customloadingscreen",
    "inventorytweaks",
    "mousetweaks",
    "journeymap",
    "mapwriter",
    "voxelmap",
    "loadingprofiler",
)

_FORGE_HEADLESS_JAVA_OPTS = (
    "-Djava.awt.headless=true",
)


class JvmRecipeExportError(RuntimeError):
    pass


class JvmRecipeExportService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._export_locks: dict[str, threading.Lock] = {}
        self._export_locks_guard = threading.Lock()

    def _export_lock_for(self, version: str) -> threading.Lock:
        with self._export_locks_guard:
            lock = self._export_locks.get(version)
            if lock is None:
                lock = threading.Lock()
                self._export_locks[version] = lock
            return lock

    def recipe_dir(self, version: str, profile_id: str | None = None) -> Path:
        return version_service.recipe_dir(version, profile_id)

    def needs_export(self, version: str, profile_id: str | None = None) -> bool:
        if recipe_layout_for_version(version) != "jvm":
            return False
        recipe_dir = self.recipe_dir(version, profile_id)
        return not any(
            path
            for path in recipe_dir.glob("*.json")
            if not path.name.startswith("_")
        )

    def ensure_exported(
        self,
        version: str,
        *,
        profile_id: str | None = None,
        force: bool = False,
    ) -> int:
        if recipe_layout_for_version(version) != "jvm":
            return 0

        recipe_dir = self.recipe_dir(version, profile_id)
        recipe_dir.mkdir(parents=True, exist_ok=True)

        if not force and not self.needs_export(version, profile_id):
            self.ensure_ae2_recipes_synced(version, profile_id=profile_id)
            return len(
                [
                    path
                    for path in recipe_dir.glob("*.json")
                    if not path.name.startswith("_")
                ]
            )

        lock = self._export_lock_for(version)
        with lock:
            if not force and not self.needs_export(version, profile_id):
                self.ensure_ae2_recipes_synced(version, profile_id=profile_id)
                return len(
                    [
                        path
                        for path in recipe_dir.glob("*.json")
                        if not path.name.startswith("_")
                    ]
                )

            client_jar = version_service.client_jar_path(version)
            mods_dir = version_service.mods_dir(version, profile_id)
            if not client_jar.is_file():
                raise JvmRecipeExportError(f"client.jar not found for version {version}")

            if version.startswith("1.7"):
                resolved_profile = version_service._resolve_profile_id(version, profile_id)
                return self._run_forge_export(
                    version,
                    client_jar,
                    mods_dir,
                    recipe_dir,
                    profile_id=resolved_profile,
                    force=force,
                )

            exporter_jar = self._resolve_exporter_jar(version)
            if exporter_jar is None:
                logger.warning(
                    "JVM recipe exporter jar not found for Minecraft {}. "
                    "Build recipe-exporter and place the jar under recipe-exporter/dist/.",
                    version,
                )
                return 0

            return self._run_java_jar_exporter(
                exporter_jar, version, client_jar, mods_dir, recipe_dir
            )

    def _run_forge_export(
        self,
        version: str,
        client_jar: Path,
        mods_dir: Path,
        recipe_dir: Path,
        *,
        profile_id: str,
        force: bool = False,
    ) -> int:
        forge_build = self._resolve_profile_forge_build(version, profile_id)
        mode = self._settings.recipe_exporter_mode.strip().lower()
        if mode in {"auto", "docker"}:
            try:
                return self._run_http_exporter(
                    version,
                    recipe_dir,
                    force=force,
                    profile_id=profile_id,
                )
            except JvmRecipeExportError:
                if mode == "docker":
                    raise
                logger.info(
                    "Docker recipe exporter unavailable for {}, falling back to universal Forge",
                    version,
                )
            except httpx.HTTPError as exc:
                if mode == "docker":
                    raise JvmRecipeExportError(
                        f"Recipe exporter HTTP request failed: {exc}"
                    ) from exc
                logger.info(
                    "Docker recipe exporter unreachable for {} ({}), falling back to universal Forge",
                    version,
                    exc,
                )

        if mode == "skip":
            logger.warning("Recipe export skipped for {} (RECIPE_EXPORTER_MODE=skip)", version)
            return 0

        if mode in {"auto", "universal"}:
            try:
                return self._run_universal_forge_export(
                    version,
                    mods_dir=mods_dir,
                    recipe_dir=recipe_dir,
                    version_dir=client_jar.parent,
                    forge_build=forge_build,
                    profile_id=profile_id,
                )
            except JvmRecipeExportError as exc:
                if mode == "universal":
                    raise
                if version.startswith("1.7"):
                    raise JvmRecipeExportError(
                        f"Экспорт через universal Forge не удался: {exc}"
                    ) from exc
                logger.info(
                    "Universal Forge export unavailable for {} ({}), falling back to Gradle dev server",
                    version,
                    exc,
                )

        project_dir = self._forge_project_dir(version)
        gradlew = self._gradlew_path(project_dir)
        if gradlew is None:
            raise JvmRecipeExportError(
                f"Forge exporter project not found for {version}. "
                f"Expected Gradle project at {project_dir}"
            )

        command = [
            str(gradlew),
            "runExport",
            f"-PoutputDir={recipe_dir.resolve()}",
            f"-PmodsDir={mods_dir.resolve()}",
            "--no-daemon",
        ]

        logger.info("Running Forge recipe export for {}: {}", version, " ".join(command))
        env = os.environ.copy()
        headless_opts = " ".join(_FORGE_HEADLESS_JAVA_OPTS)
        existing_tool_options = env.get("JAVA_TOOL_OPTIONS", "")
        if "java.awt.headless" not in existing_tool_options:
            env["JAVA_TOOL_OPTIONS"] = f"{existing_tool_options} {headless_opts}".strip()
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,
                cwd=project_dir,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise JvmRecipeExportError(detail or "Forge recipe export failed") from exc
        except subprocess.TimeoutExpired as exc:
            raise JvmRecipeExportError("Forge recipe export timed out") from exc

        if completed.stdout.strip():
            logger.info("Forge exporter stdout:\n{}", completed.stdout.strip())
        if completed.stderr.strip():
            logger.info("Forge exporter stderr:\n{}", completed.stderr.strip())

        exported = len(
            [
                path
                for path in recipe_dir.glob("*.json")
                if not path.name.startswith("_")
            ]
        )
        logger.info("Forge recipe export for {} finished with {} recipe file(s)", version, exported)
        self._finalize_export_status(version, profile_id=profile_id)
        return exported

    def _resolve_profile_forge_build(self, version: str, profile_id: str) -> str | None:
        profile_dir = version_service.profile_dir(version, profile_id)
        return resolve_profile_forge_build(profile_dir, minecraft_version=version)

    def _run_universal_forge_export(
        self,
        version: str,
        *,
        mods_dir: Path,
        recipe_dir: Path,
        version_dir: Path,
        forge_build: str | None = None,
        profile_id: str | None = None,
    ) -> int:
        forge_jar = self._ensure_universal_forge_installed(version, forge_build=forge_build)
        exporter_jar = self._ensure_exporter_mod_jar(version)
        forge_dir = forge_jar.parent
        self._sync_mods_for_universal_forge(forge_dir, mods_dir, exporter_jar)

        ore_dict_path = version_dir / "ore_dict.json"
        item_catalog_path = version_dir / "item_catalog.json"
        java_executable = self._resolve_java8_executable()
        command = [
            java_executable,
            *_FORGE_HEADLESS_JAVA_OPTS,
            "-Xmx4G",
            "-Drtv.recipe.export=true",
            f"-Drtv.recipe.export.dir={self._java_property_path(recipe_dir)}",
            f"-Drtv.ore.dict.export.file={self._java_property_path(ore_dict_path)}",
            f"-Drtv.item.catalog.export.file={self._java_property_path(item_catalog_path)}",
            "-jar",
            str(forge_jar),
            "nogui",
        ]

        installer_version = (
            forge_installer_version(version, forge_build)
            if forge_build
            else _LEGACY_FORGE_VERSION
        )
        logger.info(
            "Running universal Forge {} export for {}: {}",
            installer_version,
            version,
            " ".join(command),
        )
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,
                cwd=forge_dir,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise JvmRecipeExportError(detail or "Universal Forge recipe export failed") from exc
        except subprocess.TimeoutExpired as exc:
            raise JvmRecipeExportError("Universal Forge recipe export timed out") from exc

        if completed.stdout.strip():
            logger.info("Universal Forge exporter stdout:\n{}", completed.stdout.strip())
        if completed.stderr.strip():
            logger.info("Universal Forge exporter stderr:\n{}", completed.stderr.strip())

        exported = len(
            [
                path
                for path in recipe_dir.glob("*.json")
                if not path.name.startswith("_")
            ]
        )
        logger.info(
            "Universal Forge recipe export for {} finished with {} recipe file(s)",
            version,
            exported,
        )
        self._sync_ae2_recipe_files(version, recipe_dir, forge_build=forge_build)
        self._finalize_export_status(version, profile_id=profile_id)
        return exported

    def _run_http_exporter(
        self,
        version: str,
        recipe_dir: Path,
        *,
        force: bool = False,
        profile_id: str | None = None,
    ) -> int:
        exporter_url = self._settings.recipe_exporter_url.strip()
        if not exporter_url:
            raise JvmRecipeExportError("RECIPE_EXPORTER_URL is not configured")

        resolved_profile = version_service._resolve_profile_id(version, profile_id)
        endpoint = f"{exporter_url.rstrip('/')}/export"
        payload = {
            "version": version,
            "force": force,
            "profile_id": resolved_profile,
        }
        timeout = httpx.Timeout(self._settings.recipe_exporter_timeout_seconds)

        logger.info("Requesting Forge recipe export for {} via {}", version, endpoint)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, json=payload)
            if response.status_code == 409:
                raise JvmRecipeExportError("Recipe export already in progress")
            if response.status_code >= 400:
                detail = response.text.strip() or response.reason_phrase
                raise JvmRecipeExportError(detail or "Recipe exporter returned an error")
            data = response.json()

        status = str(data.get("status", ""))
        if status == "skipped":
            exported = int(data.get("exported", 0))
            logger.info(
                "Recipe export for {} skipped by exporter ({} file(s) already present)",
                version,
                exported,
            )
            return exported
        if status != "ok":
            error = str(data.get("error", "Recipe export failed"))
            raise JvmRecipeExportError(error)

        exported = int(data.get("exported", 0))
        if exported <= 0:
            exported = len(
                [
                    path
                    for path in recipe_dir.glob("*.json")
                    if not path.name.startswith("_")
                ]
            )
        logger.info(
            "HTTP recipe export for {} finished with {} recipe file(s) in {}s",
            version,
            exported,
            data.get("duration_seconds", "?"),
        )
        self._finalize_export_status(version, profile_id=profile_id)
        return exported

    def _run_java_jar_exporter(
        self,
        exporter_jar: Path,
        version: str,
        client_jar: Path,
        mods_dir: Path,
        recipe_dir: Path,
    ) -> int:
        command = [
            "java",
            "-jar",
            str(exporter_jar),
            "--minecraft-version",
            version,
            "--client-jar",
            str(client_jar),
            "--mods-dir",
            str(mods_dir),
            "--output-dir",
            str(recipe_dir),
        ]

        logger.info("Running JVM recipe export for {}: {}", version, " ".join(command))
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise JvmRecipeExportError(detail or "JVM recipe export failed") from exc
        except subprocess.TimeoutExpired as exc:
            raise JvmRecipeExportError("JVM recipe export timed out") from exc

        if completed.stdout.strip():
            logger.info("JVM exporter stdout: {}", completed.stdout.strip())

        exported = len(
            [
                path
                for path in recipe_dir.glob("*.json")
                if not path.name.startswith("_")
            ]
        )
        logger.info("JVM recipe export for {} finished with {} recipe file(s)", version, exported)
        return exported

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _java_property_path(self, path: Path) -> str:
        # Backslashes in -D values are parsed as escapes on Windows (e.g. \R, \M).
        return path.resolve().as_posix()

    def _resolve_java8_executable(self) -> str:
        env_home = os.environ.get("FORGE_JAVA_HOME") or os.environ.get("JAVA8_HOME")
        candidates: list[Path] = []
        if env_home:
            candidates.append(Path(env_home))

        gradle_props = Path.home() / ".gradle" / "gradle.properties"
        if gradle_props.is_file():
            match = re.search(
                r"org\.gradle\.java\.installations\.paths\s*=\s*(.+)",
                gradle_props.read_text(encoding="utf-8", errors="replace"),
            )
            if match:
                for raw_path in match.group(1).split(","):
                    candidates.append(Path(raw_path.strip().strip('"')))

        if sys.platform.startswith("win"):
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            candidates.extend(
                Path(program_files) / name
                for name in (
                    "Eclipse Adoptium/jdk-8.0.492.9-hotspot",
                    "Java/jdk1.8.0_202",
                    "Eclipse Adoptium/jdk-8.0.402.8-hotspot",
                )
            )
            for pattern in (
                r"C:\Program Files\Eclipse Adoptium\jdk-8*",
                r"C:\Program Files\Java\jdk1.8*",
            ):
                candidates.extend(Path(path) for path in sorted(glob.glob(pattern)))

        for candidate in candidates:
            java_path = candidate / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
            if java_path.is_file():
                logger.info("Using Java 8 for Forge export: {}", java_path)
                return str(java_path)

        which_java = shutil.which("java")
        if which_java:
            logger.warning(
                "Java 8 not found (set FORGE_JAVA_HOME). Falling back to PATH java: {}",
                which_java,
            )
            return which_java
        raise JvmRecipeExportError(
            "Java 8 is required for Minecraft 1.7.10 Forge export. "
            "Install Temurin JDK 8 and set FORGE_JAVA_HOME."
        )

    def _universal_forge_dir(self, version: str, *, forge_build: str | None = None) -> Path:
        return forge_install_service.universal_forge_dir(version, forge_build=forge_build)

    def _find_universal_forge_jar(self, forge_dir: Path) -> Path | None:
        return forge_install_service.find_universal_forge_jar(forge_dir)

    def _ensure_universal_forge_installed(
        self,
        version: str,
        *,
        forge_build: str | None = None,
    ) -> Path:
        try:
            return forge_install_service.ensure_installed(version, forge_build=forge_build)
        except ForgeInstallError as exc:
            raise JvmRecipeExportError(str(exc)) from exc

    def _ensure_exporter_mod_jar(self, version: str) -> Path:
        exporter_jar = self._resolve_exporter_jar(version)
        if exporter_jar is not None:
            return exporter_jar

        project_dir = self._forge_project_dir(version)
        gradlew = self._gradlew_path(project_dir)
        if gradlew is None:
            raise JvmRecipeExportError(
                "Recipe exporter mod jar is missing. "
                f"Run Gradle build in {project_dir} first."
            )

        logger.info("Building recipe-exporter mod jar via Gradle")
        subprocess.run(
            [str(gradlew), "build", "--no-daemon"],
            check=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        exporter_jar = self._resolve_exporter_jar(version)
        if exporter_jar is None:
            raise JvmRecipeExportError("Gradle build did not produce recipe-exporter mod jar")
        return exporter_jar

    def _sync_mods_for_universal_forge(
        self,
        forge_dir: Path,
        mods_dir: Path,
        exporter_jar: Path,
    ) -> None:
        target_mods = forge_dir / "mods"
        if target_mods.is_dir():
            try:
                shutil.rmtree(target_mods)
            except PermissionError:
                for jar_path in target_mods.glob("*.jar"):
                    self._safe_unlink(jar_path)
        target_mods.mkdir(parents=True, exist_ok=True)

        shutil.copy2(exporter_jar, target_mods / exporter_jar.name)
        if not mods_dir.is_dir():
            return

        skipped: list[str] = []
        skipped_client_only: list[str] = []
        for jar_path in sorted(mods_dir.glob("*.jar")):
            if jar_path.name.lower().startswith("rtv-recipe-exporter"):
                continue
            if self._is_client_only_forge_export_mod(jar_path.name):
                skipped_client_only.append(jar_path.name)
                continue
            if self._should_skip_forge_export_mod(jar_path.name):
                skipped.append(jar_path.name)
                continue
            if not zipfile.is_zipfile(jar_path):
                skipped.append(jar_path.name)
                logger.warning(
                    "Skipping corrupt mod jar for JVM export: {}",
                    jar_path.name,
                )
                continue
            shutil.copy2(jar_path, target_mods / jar_path.name)

        if skipped_client_only:
            logger.info(
                "Skipped {} client-only mod jar(s) for JVM export: {}",
                len(skipped_client_only),
                ", ".join(skipped_client_only),
            )
        if skipped:
            logger.info(
                "Skipped {} mod jar(s) for JVM export (DepLoader / library mods): {}",
                len(skipped),
                ", ".join(skipped),
            )

    @staticmethod
    def _is_client_only_forge_export_mod(jar_name: str) -> bool:
        lowered = jar_name.lower()
        return any(fragment in lowered for fragment in _FORGE_EXPORT_CLIENT_ONLY_FRAGMENTS)

    @staticmethod
    def _should_skip_forge_export_mod(jar_name: str) -> bool:
        lowered = jar_name.lower()
        return any(fragment in lowered for fragment in _FORGE_EXPORT_MOD_SKIP_FRAGMENTS)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        for attempt in range(6):
            try:
                path.unlink()
                return
            except FileNotFoundError:
                return
            except PermissionError as exc:
                if attempt >= 5:
                    raise JvmRecipeExportError(
                        f"Файл занят другим процессом (вероятно, идёт JVM-экспорт): {path.name}. "
                        "Дождитесь завершения экспорта или перезапустите backend."
                    ) from exc
                time.sleep(0.5 * (attempt + 1))

    def _sync_ae2_recipe_files(
        self,
        version: str,
        recipe_dir: Path,
        *,
        forge_build: str | None = None,
    ) -> int:
        source_root = (
            self._universal_forge_dir(version, forge_build=forge_build)
            / "config"
            / "AppliedEnergistics2"
            / "recipes"
            / "generated"
        )
        if not source_root.is_dir():
            return 0

        target_root = recipe_dir / "ae2-recipes"
        target_root.mkdir(parents=True, exist_ok=True)
        copied = 0
        for recipe_file in source_root.rglob("*.recipe"):
            relative = recipe_file.relative_to(source_root)
            destination = target_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipe_file, destination)
            copied += 1

        if copied:
            logger.info(
                "Synced {} AE2 recipe file(s) to {}",
                copied,
                target_root,
            )
            from app.recipes.manager import recipe_manager

            recipe_manager._clear_caches()
        return copied

    def ensure_ae2_recipes_synced(self, version: str, profile_id: str | None = None) -> int:
        if recipe_layout_for_version(version) != "jvm":
            return 0
        recipe_dir = self.recipe_dir(version, profile_id)
        ae2_dir = recipe_dir / "ae2-recipes"
        if any(ae2_dir.rglob("*.recipe")):
            return len(list(ae2_dir.rglob("*.recipe")))
        forge_build = self._resolve_profile_forge_build(
            version,
            version_service._resolve_profile_id(version, profile_id),
        )
        return self._sync_ae2_recipe_files(version, recipe_dir, forge_build=forge_build)

    def _forge_project_dir(self, version: str) -> Path:
        return self._repo_root() / "recipe-exporter" / "versions" / version

    def _gradlew_path(self, project_dir: Path) -> Path | None:
        if not project_dir.is_dir():
            return None
        if sys.platform.startswith("win"):
            candidate = project_dir / "gradlew.bat"
        else:
            candidate = project_dir / "gradlew"
        return candidate if candidate.is_file() else None

    def _resolve_exporter_jar(self, version: str) -> Path | None:
        candidates = (
            self._repo_root() / "recipe-exporter" / "dist" / f"recipe-exporter-{version}.jar",
            self._repo_root() / "recipe-exporter" / "dist" / "recipe-exporter-all.jar",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def export_manifest_path(self, version: str, profile_id: str | None = None) -> Path:
        return self.recipe_dir(version, profile_id) / "_export_manifest.json"

    def read_manifest(self, version: str, profile_id: str | None = None) -> dict[str, object]:
        path = self.export_manifest_path(version, profile_id)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _finalize_export_status(self, version: str, profile_id: str | None = None) -> None:
        from app.services.jvm_export_status_service import recipe_export_status_service

        recipe_export_status_service.log_warnings(version, profile_id=profile_id)

    def clear_exported_recipes(
        self,
        version: str,
        *,
        profile_id: str | None = None,
        include_ore_dict: bool = True,
    ) -> tuple[int, bool]:
        if recipe_layout_for_version(version) != "jvm":
            raise JvmRecipeExportError(
                f"Очистка экспортированных рецептов поддерживается только для JVM-версий (получено {version})"
            )

        resolved_profile = version_service._resolve_profile_id(version, profile_id)
        from app.services.profile_storage import profile_storage_key

        storage_key = profile_storage_key(version, resolved_profile)

        deleted = 0
        recipe_dir = self.recipe_dir(version, resolved_profile)
        if recipe_dir.is_dir():
            for path in recipe_dir.glob("*.json"):
                path.unlink(missing_ok=True)
                deleted += 1

        ore_dict_removed = False
        if include_ore_dict:
            ore_dict_path = self._settings.minecraft_versions_path / version / "ore_dict.json"
            if ore_dict_path.is_file():
                ore_dict_path.unlink()
                ore_dict_removed = True

        from app.recipes.manager import recipe_manager
        from app.services.mod_service import mod_service

        recipe_manager._clear_caches()
        mod_service._loaded_versions.discard(storage_key)
        return deleted, ore_dict_removed


jvm_recipe_export_service = JvmRecipeExportService()
