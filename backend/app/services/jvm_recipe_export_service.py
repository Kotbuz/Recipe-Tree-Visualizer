from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import glob
from pathlib import Path

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version

_LEGACY_FORGE_VERSION = "1.7.10-10.13.4.1448-1.7.10"

# (install_group, artifact, version, optional_direct_download_url)
_FORGE_INSTALLER_LIBRARIES: tuple[tuple[str, str, str, str | None], ...] = (
    ("com.typesafe.akka", "akka-actor_2.11", "2.3.3", None),
    ("com.typesafe", "config", "1.2.1", None),
    ("org.scala-lang", "scala-actors-migration_2.11", "1.1.0", None),
    ("org.scala-lang", "scala-compiler", "2.11.1", None),
    ("org.scala-lang.plugins", "scala-continuations-library_2.11", "1.0.2", None),
    ("org.scala-lang.plugins", "scala-continuations-plugin_2.11.1", "1.0.2", None),
    ("org.scala-lang", "scala-library", "2.11.1", None),
    (
        "org.scala-lang",
        "scala-parser-combinators_2.11",
        "1.0.1",
        "https://repo1.maven.org/maven2/org/scala-lang/modules/scala-parser-combinators_2.11/1.0.1/scala-parser-combinators_2.11-1.0.1.jar",
    ),
    ("org.scala-lang", "scala-reflect", "2.11.1", None),
    (
        "org.scala-lang",
        "scala-swing_2.11",
        "1.0.1",
        "https://maven.minecraftforge.net/org/scala-lang/scala-swing_2.11/1.0.1/scala-swing_2.11-1.0.1.jar",
    ),
    (
        "org.scala-lang",
        "scala-xml_2.11",
        "1.0.2",
        "https://repo1.maven.org/maven2/org/scala-lang/modules/scala-xml_2.11/1.0.2/scala-xml_2.11-1.0.2.jar",
    ),
)


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
            self.ensure_ae2_recipes_synced(version)
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

    def _run_universal_forge_export(
        self,
        version: str,
        *,
        mods_dir: Path,
        recipe_dir: Path,
        version_dir: Path,
    ) -> int:
        forge_jar = self._ensure_universal_forge_installed(version)
        exporter_jar = self._ensure_exporter_mod_jar(version)
        forge_dir = forge_jar.parent
        self._sync_mods_for_universal_forge(forge_dir, mods_dir, exporter_jar)

        ore_dict_path = version_dir / "ore_dict.json"
        item_catalog_path = version_dir / "item_catalog.json"
        java_executable = self._resolve_java8_executable()
        command = [
            java_executable,
            "-Xmx4G",
            "-Drtv.recipe.export=true",
            f"-Drtv.recipe.export.dir={self._java_property_path(recipe_dir)}",
            f"-Drtv.ore.dict.export.file={self._java_property_path(ore_dict_path)}",
            f"-Drtv.item.catalog.export.file={self._java_property_path(item_catalog_path)}",
            "-jar",
            str(forge_jar),
            "nogui",
        ]

        logger.info(
            "Running universal Forge {} export for {}: {}",
            _LEGACY_FORGE_VERSION,
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
        self._sync_ae2_recipe_files(version, recipe_dir)
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

    def _universal_forge_dir(self, version: str) -> Path:
        return self._repo_root() / "recipe-exporter" / "forge-runtime" / version

    def _find_universal_forge_jar(self, forge_dir: Path) -> Path | None:
        jars = sorted(forge_dir.glob("forge-*-universal.jar"))
        return jars[0] if jars else None

    def _ensure_universal_forge_installed(self, version: str) -> Path:
        forge_dir = self._universal_forge_dir(version)
        forge_dir.mkdir(parents=True, exist_ok=True)

        existing = self._find_universal_forge_jar(forge_dir)
        if existing is not None:
            return existing

        forge_version = _LEGACY_FORGE_VERSION
        installer_name = f"forge-{forge_version}-installer.jar"
        installer_path = forge_dir / installer_name
        logger.info("Downloading Forge {} to {}", forge_version, forge_dir)
        installer_url = (
            "https://maven.minecraftforge.net/net/minecraftforge/forge/"
            f"{forge_version}/{installer_name}"
        )
        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(300.0)) as client:
            response = client.get(
                installer_url,
                headers={"User-Agent": "Recipe-Tree-Visualizer/1.0"},
            )
            response.raise_for_status()
            installer_path.write_bytes(response.content)
            self._bootstrap_forge_installer_libraries(forge_dir, client)

        try:
            completed = subprocess.run(
                [self._resolve_java8_executable(), "-jar", str(installer_path), "--installServer"],
                check=True,
                cwd=forge_dir,
                capture_output=True,
                text=True,
                timeout=900,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise JvmRecipeExportError(
                "Не удалось установить Forge universal server "
                f"({forge_version}). {detail}"
            ) from exc
        finally:
            installer_path.unlink(missing_ok=True)
        (forge_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")

        universal = self._find_universal_forge_jar(forge_dir)
        if universal is None:
            raise JvmRecipeExportError(
                f"Forge universal jar not found after install in {forge_dir}"
            )
        return universal

    def _bootstrap_forge_installer_libraries(self, forge_dir: Path, client: httpx.Client) -> None:
        libraries_dir = forge_dir / "libraries"
        headers = {"User-Agent": "Recipe-Tree-Visualizer/1.0"}
        for group, artifact, version, direct_url in _FORGE_INSTALLER_LIBRARIES:
            jar_name = f"{artifact}-{version}.jar"
            destination = libraries_dir / group.replace(".", "/") / artifact / version / jar_name
            if destination.is_file():
                continue
            if direct_url:
                url = direct_url
            else:
                url = (
                    "https://repo1.maven.org/maven2/"
                    f"{group.replace('.', '/')}/{artifact}/{version}/{jar_name}"
                )
            response = client.get(url, headers=headers)
            if response.status_code == 404:
                logger.warning("Forge bootstrap library not found: {}", url)
                continue
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            logger.info("Bootstrapped Forge library {}", jar_name)

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
        target_mods.mkdir(parents=True, exist_ok=True)
        for jar_path in target_mods.glob("*.jar"):
            jar_path.unlink()

        shutil.copy2(exporter_jar, target_mods / exporter_jar.name)
        if not mods_dir.is_dir():
            return

        for jar_path in sorted(mods_dir.glob("*.jar")):
            if jar_path.name.lower().startswith("rtv-recipe-exporter"):
                continue
            shutil.copy2(jar_path, target_mods / jar_path.name)

    def _sync_ae2_recipe_files(self, version: str, recipe_dir: Path) -> int:
        source_root = (
            self._universal_forge_dir(version)
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

    def ensure_ae2_recipes_synced(self, version: str) -> int:
        if recipe_layout_for_version(version) != "jvm":
            return 0
        recipe_dir = self.recipe_dir(version)
        ae2_dir = recipe_dir / "ae2-recipes"
        if any(ae2_dir.rglob("*.recipe")):
            return len(list(ae2_dir.rglob("*.recipe")))
        return self._sync_ae2_recipe_files(version, recipe_dir)

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

    def clear_exported_recipes(self, version: str, *, include_ore_dict: bool = True) -> tuple[int, bool]:
        if recipe_layout_for_version(version) != "jvm":
            raise JvmRecipeExportError(
                f"Очистка экспортированных рецептов поддерживается только для JVM-версий (получено {version})"
            )

        deleted = 0
        recipe_dir = self.recipe_dir(version)
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
        mod_service._loaded_versions.discard(version)
        return deleted, ore_dict_removed


jvm_recipe_export_service = JvmRecipeExportService()
