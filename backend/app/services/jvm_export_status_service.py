from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from app.core.config import get_settings
from app.core.recipe_layout import recipe_layout_for_version
from app.services.version_service import version_service

_FORGE_1710_DEPENDENCIES: dict[str, list[str]] = {
    # На 1.7.10 CodeChickenLib заменяет CodeChickenCore для ChickenBones-модов.
    "forgemultipart": ["CodeChickenLib"],
    "thaumcraft": ["Baubles"],
    "thermalexpansion": ["CoFHCore", "ThermalFoundation"],
    "buildcraft": ["BuildCraft|Core"],
}

_CLASS_NOT_FOUND = re.compile(r"ClassNotFoundException:\s*(\S+)")
_MOD_EXCEPTION = re.compile(r"Caught exception from (\w+)", re.IGNORECASE)
_LOADER_EXCEPTION = re.compile(r"LoaderException:\s*(.+)")
_FORGE_ERROR_LINE = re.compile(r"\[.*ERROR.*\]:\s*(.+)")
_MISSING_MODS_BLOCK = re.compile(r"Missing Mods:\s*\n((?:\t\S+.*\n)+)", re.MULTILINE)
_FORGE_VERSION_REQUIREMENT = re.compile(
    r"^\s*Forge\s*:\s*\[(?P<version>[^\],)]+)",
    re.MULTILINE,
)
_FORGE_LOADED_VERSION = re.compile(
    r"Minecraft Forge\s+(?P<version>\d+\.\d+\.\d+\.\d+)",
    re.IGNORECASE,
)

# dependency_name (normalized) -> jar name fragments that satisfy it
_DEPENDENCY_SATISFIED_BY: dict[str, tuple[str, ...]] = {
    "codechickencore": ("codechickenlib", "codechickencore"),
}

# Библиотеки / API-моды без собственных рецептов крафта в экспорте.
_LIBRARY_MOD_IDS = frozenset(
    {
        "codechickencore",
        "codechickenlib",
        "forgemultipart",
        "forgemultipartcbe",
    }
)


@dataclass(frozen=True)
class ModDependencyIssue:
    mod_id: str
    jar_name: str
    missing_dependencies: tuple[str, ...]


@dataclass(frozen=True)
class RecipeExportStatus:
    version: str
    layout: str
    exported_recipe_count: int
    installed_mod_jars: tuple[str, ...]
    recipe_mod_ids: tuple[str, ...]
    mods_without_recipes: tuple[str, ...]
    missing_dependencies: tuple[ModDependencyIssue, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    log_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_manifest_payload(self) -> dict[str, object]:
        return {
            "mods_installed": list(self.installed_mod_jars),
            "recipe_mod_ids": list(self.recipe_mod_ids),
            "mods_without_recipes": list(self.mods_without_recipes),
            "missing_dependencies": [
                {
                    "mod_id": issue.mod_id,
                    "jar_name": issue.jar_name,
                    "requires": list(issue.missing_dependencies),
                }
                for issue in self.missing_dependencies
            ],
            "warnings": list(self.warnings),
            "log_errors": list(self.log_errors),
        }


from app.parser.jar_meta import (  # noqa: E402  # circular import guard
    guess_mod_id_from_jar_filename as _guess_mod_id_from_jar_filename,
)


def _guess_mod_id(jar_name: str) -> str:
    return _guess_mod_id_from_jar_filename(jar_name)


def _jar_provides_dependency(jar_name: str, dependency: str) -> bool:
    jar_normalized = jar_name.lower().replace("_", "").replace("-", "")
    dep_lower = dependency.lower().replace("|", "").replace("_", "").replace("-", "")
    if dep_lower in jar_normalized:
        return True
    if "|" in dependency:
        prefix = dependency.split("|", 1)[0].lower().replace("_", "").replace("-", "")
        if prefix and prefix in jar_normalized:
            return True
    for alias in _DEPENDENCY_SATISFIED_BY.get(dep_lower, ()):
        if alias.replace("_", "").replace("-", "") in jar_normalized:
            return True
    return False


def _extract_forge_version_requirement(text: str) -> str | None:
    match = _FORGE_VERSION_REQUIREMENT.search(text)
    if not match:
        return None
    return match.group("version").strip()


def _extract_loaded_forge_version(text: str) -> str | None:
    match = _FORGE_LOADED_VERSION.search(text)
    if not match:
        return None
    return match.group("version").strip()


def _extract_missing_mods_from_diagnostic(text: str) -> list[str]:
    match = _MISSING_MODS_BLOCK.search(text)
    if not match:
        return []
    missing: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        mod_id = stripped.split(":", 1)[0].strip()
        if mod_id.lower() == "forge":
            continue
        if mod_id and mod_id not in missing:
            missing.append(mod_id)
    return missing


def _list_installed_mod_jars(mods_dir: Path) -> list[str]:
    if not mods_dir.is_dir():
        return []
    return sorted(path.name for path in mods_dir.glob("*.jar") if path.is_file())


def _recipe_namespaces(recipe_dir: Path) -> set[str]:
    namespaces: set[str] = set()
    if not recipe_dir.is_dir():
        return namespaces

    for path in recipe_dir.glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        recipe_id = payload.get("id")
        if isinstance(recipe_id, str) and ":" in recipe_id:
            namespaces.add(recipe_id.split(":", 1)[0].lower())
            continue
        if "__" in path.stem:
            namespaces.add(path.stem.split("__", 1)[0].lower())
    return namespaces


def _find_missing_dependencies(
    jar_names: list[str],
) -> list[ModDependencyIssue]:
    issues: list[ModDependencyIssue] = []
    for jar_name in jar_names:
        mod_id = _guess_mod_id(jar_name)
        required = _FORGE_1710_DEPENDENCIES.get(mod_id)
        if not required:
            continue
        missing = [
            dependency
            for dependency in required
            if not any(_jar_provides_dependency(installed, dependency) for installed in jar_names)
        ]
        if missing:
            issues.append(
                ModDependencyIssue(
                    mod_id=mod_id,
                    jar_name=jar_name,
                    missing_dependencies=tuple(missing),
                )
            )
    return issues


def _forge_log_candidates(version: str, forge_build: str | None = None) -> list[Path]:
    settings = get_settings()
    repo_root = settings.minecraft_versions_path.parent
    if not repo_root.is_dir():
        repo_root = Path(__file__).resolve().parents[2]
    if forge_build:
        return [
            repo_root
            / "recipe-exporter"
            / "forge-runtime"
            / version
            / forge_build
            / "logs"
            / "latest.log",
        ]
    return [
        repo_root / "recipe-exporter" / "forge-runtime" / version / "logs" / "latest.log",
        repo_root / "recipe-exporter" / "versions" / version / "run" / "logs" / "latest.log",
    ]


def _forge_log_path(version: str, forge_build: str | None = None) -> Path:
    for candidate in _forge_log_candidates(version, forge_build=forge_build):
        if candidate.is_file():
            return candidate
    return _forge_log_candidates(version, forge_build=forge_build)[0]


def _forge_crash_report_candidates(version: str, forge_build: str | None = None) -> list[Path]:
    return [
        path.parent.parent / "crash-reports"
        for path in _forge_log_candidates(version, forge_build=forge_build)
    ]


def _latest_crash_report_text(version: str, forge_build: str | None = None) -> str:
    reports: list[Path] = []
    for crash_dir in _forge_crash_report_candidates(version, forge_build=forge_build):
        if not crash_dir.is_dir():
            continue
        reports.extend(
            sorted(
                crash_dir.glob("crash-*.txt"), key=lambda path: path.stat().st_mtime, reverse=True
            )
        )
    if not reports:
        return ""
    return reports[0].read_text(encoding="utf-8", errors="replace")


def _forge_diagnostic_text(
    version: str,
    log_path: Path | None = None,
    *,
    forge_build: str | None = None,
) -> str:
    parts: list[str] = []
    resolved_log = log_path or _forge_log_path(version, forge_build=forge_build)
    if resolved_log.is_file():
        parts.append(resolved_log.read_text(encoding="utf-8", errors="replace"))
    crash_text = _latest_crash_report_text(version, forge_build=forge_build)
    if crash_text:
        parts.append(crash_text)
    return "\n".join(parts)


def _parse_forge_log(log_path: Path) -> tuple[list[str], list[str]]:
    if not log_path.is_file():
        return [], []

    text = log_path.read_text(encoding="utf-8", errors="replace")
    class_errors = sorted(set(_CLASS_NOT_FOUND.findall(text)))
    mod_errors = sorted(set(_MOD_EXCEPTION.findall(text)))
    return class_errors, mod_errors


def _extract_forge_loader_errors(
    log_path: Path,
    *,
    version: str | None = None,
    forge_build: str | None = None,
) -> list[str]:
    text = ""
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
    if version is not None:
        text = _forge_diagnostic_text(version, log_path, forge_build=forge_build)
    elif not text:
        return []

    messages: list[str] = []
    seen: set[str] = set()

    def add(message: str) -> None:
        cleaned = message.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            messages.append(cleaned)

    required_forge = _extract_forge_version_requirement(text)
    loaded_forge = _extract_loaded_forge_version(text)
    if required_forge and loaded_forge and loaded_forge != required_forge:
        add(
            f"Модпак требует Forge {required_forge} или новее, "
            f"а экспортёр запущен на {loaded_forge}. "
            "Перезапустите экспорт после установки нужной версии Forge."
        )
    elif required_forge and not loaded_forge:
        add(
            f"Модпак требует Forge {required_forge} или новее. "
            "Убедитесь, что в профиле указана версия Forge (импорт из корня инстанса Prism)."
        )

    for mod_id in _extract_missing_mods_from_diagnostic(text):
        add(
            f"Forge не запустился: отсутствует мод «{mod_id}». "
            "CurseForge zip содержит только overrides (часть jar), лаунчер ставит все моды "
            "из manifest. Импортируйте папку инстанса после установки модпака "
            "или добавьте jar вручную."
        )

    for match in _LOADER_EXCEPTION.finditer(text):
        add(match.group(1))

    for match in _FORGE_ERROR_LINE.finditer(text):
        line = match.group(1).strip()
        if "LoaderException" in line:
            continue
        if any(token in line for token in ("Exception", "Error", "incompatible", "crash")):
            add(line)

    if "IC2 is incompatible with this environment" in text:
        add(
            "IndustrialCraft 2: установлена experimental/dev-сборка — Forge не стартует. "
            "Замените на обычный IC2 для 1.7.10 или временно уберите JAR из mods/."
        )

    if "codechicken.multipart" in text and "NoSuchFieldError" in text:
        add(
            "ForgeMultipart несовместим с Forge в JVM-экспортёре. "
            "Удалите ForgeMultipart-*.jar из mods/ — для AE2 rv3-beta-6 он не обязателен."
        )

    if "ic2.core.IC2" in text and "NoSuchFieldError" in text:
        add(
            "IC2 Classic несовместим с Gradle dev-сервером (Forge 10.13.4.1614). "
            "Временно уберите IC2Classic-*.jar из mods/."
        )

    if "appeng.util.Platform" in text and "NoSuchFieldError" in text:
        add(
            "AE2 rv3-beta-6 несовместим с Gradle dev-сервером (Forge 10.13.4.1614); "
            "нужен universal Forge 10.13.4.1448. "
            "Перезапустите экспорт — бэкенд установит его автоматически."
        )

    if (
        "resourceloader" in text.lower()
        or "IResourcePack" in text
        or "net.minecraft.client.resources" in text
    ):
        add(
            "Клиентский мод (Resource Loader, Custom Main Menu и т.п.) "
            "несовместим с headless JVM-экспортом. "
            "Такие jar автоматически исключаются при экспорте — "
            "нажмите «Перезагрузить моды и рецепты»."
        )

    return messages[:8]


def _warn_incomplete_curseforge_profile(jar_names: list[str]) -> list[str]:
    lowered = [name.lower() for name in jar_names]
    ic2_dependent_fragments = (
        "galacticraft",
        "gravisuite",
        "advancedsolarpanel",
        "advancedgenetics",
    )
    has_ic2_dependent = any(
        any(fragment in name for fragment in ic2_dependent_fragments) for name in lowered
    )
    has_ic2 = any(
        "industrialcraft" in name or name.startswith("ic2-") or name.startswith("ic2_")
        for name in lowered
    )
    if has_ic2_dependent and not has_ic2:
        return [
            "Похоже на неполный CurseForge zip: есть Galacticraft/GraviSuite и др., "
            "но нет IndustrialCraft 2 (IC2). Лаунчер ставит ~117 модов из manifest, "
            "а zip overrides — только ~30 jar. Импортируйте папку инстанса из лаунчера."
        ]
    return []


def _warn_incompatible_mod_jars(jar_names: list[str]) -> list[str]:
    warnings: list[str] = []
    for jar_name in jar_names:
        lowered = jar_name.lower()
        if "industrialcraft" in lowered and "experimental" in lowered:
            warnings.append(
                f"Мод {jar_name} — experimental/dev-сборка IC2. "
                "При экспорте Forge обычно падает; используйте release IC2-2.2.x для 1.7.10."
            )
        if "ic2classic" in lowered:
            warnings.append(
                f"Мод {jar_name} (IC2 Classic) может ломать JVM-экспорт на Forge 10.13.4.1614. "
                "Для экспорта AE2 временно уберите этот JAR из mods/."
            )
    return warnings


def _build_warnings(
    *,
    jar_names: list[str],
    recipe_namespaces: set[str],
    missing_dependencies: list[ModDependencyIssue],
    log_class_errors: list[str],
    log_loader_errors: list[str],
    incompatible_jar_warnings: list[str],
    exported_count: int,
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(incompatible_jar_warnings)

    for issue in missing_dependencies:
        deps = ", ".join(issue.missing_dependencies)
        warnings.append(
            f"Мод {issue.jar_name} ({issue.mod_id}) требует зависимости: {deps}. "
            f"Добавьте их в MinecraftVersions/.../mods/ и перезапустите экспорт."
        )

    if exported_count == 0 and jar_names:
        for message in log_loader_errors[:5]:
            if message.startswith("Forge не запустился: отсутствует мод"):
                warnings.append(message)
        for message in log_loader_errors[:5]:
            if message.startswith("Forge не запустился: отсутствует мод"):
                continue
            warnings.append(f"Ошибка экспорта Forge: {message}")
        if log_loader_errors or incompatible_jar_warnings:
            warnings.append(
                "Экспорт завершился без файлов рецептов. Устраните проблемные моды и "
                "нажмите «Перезагрузить моды и рецепты»."
            )
        elif not warnings:
            warnings.append(
                "JVM-экспорт рецептов ещё не выполнен (0 файлов в recipe/). "
                "Нажмите «Перезагрузить моды и рецепты» — экспорт запустится автоматически, "
                "или запустите recipe-exporter вручную (Gradle / Docker)."
            )
        return warnings

    for jar_name in jar_names:
        mod_id = _guess_mod_id(jar_name)
        if mod_id == "minecraft" or mod_id in _LIBRARY_MOD_IDS:
            continue
        if mod_id not in recipe_namespaces:
            warnings.append(
                f"Мод {jar_name} установлен, но рецепты для «{mod_id}» не экспортированы. "
                "Вероятно, Forge не смог загрузить мод (проверьте зависимости и логи экспорта)."
            )

    for class_name in log_class_errors[:5]:
        if "codechicken" in class_name.lower():
            warnings.append(
                "В логе экспорта: возможно отсутствует CodeChickenCore или ForgeMultipart "
                f"({class_name})."
            )

    return warnings


def _recipe_dir(version: str, profile_id: str | None = None) -> Path:
    return version_service.recipe_dir(version, profile_id)


def _export_manifest_path(version: str, profile_id: str | None = None) -> Path:
    return _recipe_dir(version, profile_id) / "_export_manifest.json"


def analyze_recipe_export_status(
    version: str,
    profile_id: str | None = None,
) -> RecipeExportStatus:
    layout = recipe_layout_for_version(version)
    resolved_profile = version_service._resolve_profile_id(version, profile_id)
    mods_dir = version_service.mods_dir(version, resolved_profile)
    profile_dir = version_service.profile_dir(version, resolved_profile)
    from app.services.profile_storage import resolve_profile_forge_build

    forge_build = resolve_profile_forge_build(profile_dir, minecraft_version=version)

    jar_names = _list_installed_mod_jars(mods_dir)
    if layout != "jvm":
        return RecipeExportStatus(
            version=version,
            layout=layout,
            exported_recipe_count=0,
            installed_mod_jars=tuple(jar_names),
            recipe_mod_ids=(),
            mods_without_recipes=(),
            missing_dependencies=(),
            warnings=(),
            log_errors=(),
        )

    recipe_dir = _recipe_dir(version, resolved_profile)
    recipe_namespaces = _recipe_namespaces(recipe_dir)
    exported_count = len(
        [
            path
            for path in recipe_dir.glob("*.json")
            if path.is_file() and not path.name.startswith("_")
        ]
    )

    missing_dependencies = _find_missing_dependencies(jar_names)
    mods_without_recipes = tuple(
        sorted(
            {
                _guess_mod_id(jar_name)
                for jar_name in jar_names
                if _guess_mod_id(jar_name) not in recipe_namespaces
                and _guess_mod_id(jar_name) not in _LIBRARY_MOD_IDS
            }
        )
    )

    log_path = _forge_log_path(version, forge_build=forge_build)
    log_class_errors, log_mod_errors = _parse_forge_log(log_path)
    # After a successful export, ignore stale crash reports from the Gradle dev server.
    log_loader_errors = _extract_forge_loader_errors(
        log_path,
        version=version if exported_count == 0 else None,
        forge_build=forge_build,
    )
    incompatible_jar_warnings = _warn_incompatible_mod_jars(jar_names)
    incomplete_warnings = _warn_incomplete_curseforge_profile(jar_names)
    warnings = _build_warnings(
        jar_names=jar_names,
        recipe_namespaces=recipe_namespaces,
        missing_dependencies=missing_dependencies,
        log_class_errors=log_class_errors,
        log_loader_errors=log_loader_errors,
        incompatible_jar_warnings=incompatible_jar_warnings + incomplete_warnings,
        exported_count=exported_count,
    )

    return RecipeExportStatus(
        version=version,
        layout=layout,
        exported_recipe_count=exported_count,
        installed_mod_jars=tuple(jar_names),
        recipe_mod_ids=tuple(sorted(recipe_namespaces)),
        mods_without_recipes=mods_without_recipes,
        missing_dependencies=tuple(missing_dependencies),
        warnings=tuple(warnings),
        log_errors=tuple(
            log_loader_errors[:10]
            + [f"class:{name}" for name in log_class_errors[:5]]
            + [f"mod:{name}" for name in log_mod_errors[:5]]
        ),
    )


def refresh_export_manifest(
    version: str,
    profile_id: str | None = None,
) -> RecipeExportStatus:
    status = analyze_recipe_export_status(version, profile_id=profile_id)
    manifest_path = _export_manifest_path(version, profile_id)
    payload: dict[str, object] = {}
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
        except json.JSONDecodeError:
            pass

    payload.update(status.to_manifest_payload())
    payload["recipe_count"] = status.exported_recipe_count
    payload.setdefault("status", "ok" if status.exported_recipe_count > 0 else "empty")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return status


def log_export_warnings(version: str, profile_id: str | None = None) -> RecipeExportStatus:
    if recipe_layout_for_version(version) != "jvm":
        return RecipeExportStatus(
            version=version,
            layout=recipe_layout_for_version(version),
            exported_recipe_count=0,
            installed_mod_jars=(),
            recipe_mod_ids=(),
            mods_without_recipes=(),
            missing_dependencies=(),
        )

    status = refresh_export_manifest(version, profile_id=profile_id)
    for warning in status.warnings:
        logger.warning("[recipe-export:{}] {}", version, warning)
    return status


class RecipeExportStatusService:
    def analyze(self, version: str, profile_id: str | None = None) -> RecipeExportStatus:
        return analyze_recipe_export_status(version, profile_id=profile_id)

    def refresh_manifest(self, version: str, profile_id: str | None = None) -> RecipeExportStatus:
        return refresh_export_manifest(version, profile_id=profile_id)

    def log_warnings(self, version: str, profile_id: str | None = None) -> RecipeExportStatus:
        return log_export_warnings(version, profile_id=profile_id)


recipe_export_status_service = RecipeExportStatusService()
