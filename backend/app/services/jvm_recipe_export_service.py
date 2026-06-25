from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
        return not any(recipe_dir.glob("*.json"))

    def ensure_exported(self, version: str, *, force: bool = False) -> int:
        if recipe_layout_for_version(version) != "jvm":
            return 0

        recipe_dir = self.recipe_dir(version)
        recipe_dir.mkdir(parents=True, exist_ok=True)

        if not force and any(recipe_dir.glob("*.json")):
            return len(list(recipe_dir.glob("*.json")))

        exporter_jar = self._resolve_exporter_jar(version)
        if exporter_jar is None:
            logger.warning(
                "JVM recipe exporter jar not found for Minecraft {}. "
                "Build recipe-exporter and place the jar under recipe-exporter/dist/.",
                version,
            )
            return 0

        version_dir = self._settings.minecraft_versions_path / version
        mods_dir = version_dir / "mods"
        client_jar = version_dir / "client.jar"
        if not client_jar.is_file():
            raise JvmRecipeExportError(f"client.jar not found for version {version}")

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

        exported = len(list(recipe_dir.glob("*.json")))
        logger.info("JVM recipe export for {} finished with {} recipe file(s)", version, exported)
        return exported

    def _resolve_exporter_jar(self, version: str) -> Path | None:
        backend_root = Path(__file__).resolve().parents[2]
        repo_root = backend_root.parent
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


jvm_recipe_export_service = JvmRecipeExportService()
