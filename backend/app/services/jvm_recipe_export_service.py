from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from loguru import logger

from app.core.config import get_settings
from app.recipes.loaders.recipe_paths import recipe_layout_for_version


class JvmRecipeExportError(RuntimeError):
    pass


class JvmRecipeExportService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def recipe_dir(self, version: str) -> Path:
        return self._settings.minecraft_versions_path / version / "recipe"

    def needs_export(self, version: str) -> bool:
        if recipe_layout_for_version(version) != "jvm":
            return False
        recipe_dir = self.recipe_dir(version)
        return not any(
            path
            for path in recipe_dir.glob("*.json")
            if not path.name.startswith("_")
        )

    def ensure_exported(self, version: str, *, force: bool = False) -> int:
        if recipe_layout_for_version(version) != "jvm":
            return 0

        recipe_dir = self.recipe_dir(version)
        recipe_dir.mkdir(parents=True, exist_ok=True)

        if not force and not self.needs_export(version):
            return len(
                [
                    path
                    for path in recipe_dir.glob("*.json")
                    if not path.name.startswith("_")
                ]
            )

        version_dir = self._settings.minecraft_versions_path / version
        mods_dir = version_dir / "mods"
        client_jar = version_dir / "client.jar"
        if not client_jar.is_file():
            raise JvmRecipeExportError(f"client.jar not found for version {version}")

        if version.startswith("1.7"):
            return self._run_forge_export(
                version, client_jar, mods_dir, recipe_dir, force=force
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
        force: bool = False,
    ) -> int:
        mode = self._settings.recipe_exporter_mode.strip().lower()
        if mode in {"auto", "docker"}:
            try:
                return self._run_http_exporter(version, recipe_dir, force=force)
            except JvmRecipeExportError:
                if mode == "docker":
                    raise
                logger.info(
                    "Docker recipe exporter unavailable for {}, falling back to Gradle",
                    version,
                )
            except httpx.HTTPError as exc:
                if mode == "docker":
                    raise JvmRecipeExportError(
                        f"Recipe exporter HTTP request failed: {exc}"
                    ) from exc
                logger.info(
                    "Docker recipe exporter unreachable for {} ({}), falling back to Gradle",
                    version,
                    exc,
                )

        if mode == "skip":
            logger.warning("Recipe export skipped for {} (RECIPE_EXPORTER_MODE=skip)", version)
            return 0

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
        self._finalize_export_status(version)
        return exported

    def _run_http_exporter(
        self,
        version: str,
        recipe_dir: Path,
        *,
        force: bool = False,
    ) -> int:
        exporter_url = self._settings.recipe_exporter_url.strip()
        if not exporter_url:
            raise JvmRecipeExportError("RECIPE_EXPORTER_URL is not configured")

        endpoint = f"{exporter_url.rstrip('/')}/export"
        payload = {"version": version, "force": force}
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
        self._finalize_export_status(version)
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

    def _forge_project_dir(self, version: str) -> Path:
        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / "recipe-exporter" / "versions" / version

    def _gradlew_path(self, project_dir: Path) -> Path | None:
        if not project_dir.is_dir():
            return None
        if sys.platform.startswith("win"):
            candidate = project_dir / "gradlew.bat"
        else:
            candidate = project_dir / "gradlew"
        return candidate if candidate.is_file() else None

    def _resolve_exporter_jar(self, version: str) -> Path | None:
        repo_root = Path(__file__).resolve().parents[3]
        candidates = (
            repo_root / "recipe-exporter" / "dist" / f"recipe-exporter-{version}.jar",
            repo_root / "recipe-exporter" / "dist" / "recipe-exporter-all.jar",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def export_manifest_path(self, version: str) -> Path:
        return self.recipe_dir(version) / "_export_manifest.json"

    def read_manifest(self, version: str) -> dict[str, object]:
        path = self.export_manifest_path(version)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _finalize_export_status(self, version: str) -> None:
        from app.services.jvm_export_status_service import recipe_export_status_service

        recipe_export_status_service.log_warnings(version)


jvm_recipe_export_service = JvmRecipeExportService()
