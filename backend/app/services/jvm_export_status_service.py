from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from app.core.config import get_settings
from app.recipes.loaders.recipe_paths import recipe_layout_for_version

_FORGE_1710_DEPENDENCIES: dict[str, list[str]] = {
    "appliedenergistics2": ["CodeChickenLib", "ForgeMultipart"],
    "ae2": ["CodeChickenLib", "ForgeMultipart"],
    "thaumcraft": ["Baubles"],
    "thermalexpansion": ["CoFHCore", "ThermalFoundation"],
    "buildcraft": ["BuildCraft|Core"],
}

_JAR_MOD_ID_HINTS: tuple[tuple[str, str], ...] = (
    ("appliedenergistics2", "appliedenergistics2"),
    ("industrialcraft", "ic2"),
    ("mekanism", "mekanism"),
    ("thaumcraft", "thaumcraft"),
    ("buildcraft", "buildcraft"),
    ("thermal", "thermalfoundation"),
    ("cofh", "cofhcore"),
)

_CLASS_NOT_FOUND = re.compile(r"ClassNotFoundException:\s*(\S+)")
_MOD_EXCEPTION = re.compile(r"Caught exception from (\w+)", re.IGNORECASE)


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


def _guess_mod_id(jar_name: str) -> str:
    lowered = jar_name.lower()
    for needle, mod_id in _JAR_MOD_ID_HINTS:
        if needle in lowered:
            return mod_id
    stem = Path(jar_name).stem.lower()
    return stem.split("-", 1)[0]


def _jar_provides_dependency(jar_name: str, dependency: str) -> bool:
    jar_lower = jar_name.lower()
    dep_lower = dependency.lower().replace("|", "").replace("_", "").replace("-", "")
    return dep_lower in jar_lower.replace("_", "").replace("-", "")


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


def _parse_forge_log(log_path: Path) -> tuple[list[str], list[str]]:
    if not log_path.is_file():
        return [], []

    text = log_path.read_text(encoding="utf-8", errors="replace")
    class_errors = sorted(set(_CLASS_NOT_FOUND.findall(text)))
    mod_errors = sorted(set(_MOD_EXCEPTION.findall(text)))
    return class_errors, mod_errors


def _build_warnings(
    *,
    jar_names: list[str],
    recipe_namespaces: set[str],
    missing_dependencies: list[ModDependencyIssue],
    log_class_errors: list[str],
) -> list[str]:
    warnings: list[str] = []

    for issue in missing_dependencies:
        deps = ", ".join(issue.missing_dependencies)
        warnings.append(
            f"Мод {issue.jar_name} ({issue.mod_id}) требует зависимости: {deps}. "
            f"Добавьте их в MinecraftVersions/.../mods/ и перезапустите экспорт."
        )

    for jar_name in jar_names:
        mod_id = _guess_mod_id(jar_name)
        if mod_id == "minecraft":
            continue
        if mod_id not in recipe_namespaces:
            warnings.append(
                f"Мод {jar_name} установлен, но рецепты для «{mod_id}» не экспортированы. "
                "Вероятно, Forge не смог загрузить мод (проверьте зависимости и логи экспорта)."
            )

    for class_name in log_class_errors[:5]:
        if "codechicken" in class_name.lower():
            warnings.append(
                "В логе экспорта: отсутствует CodeChickenLib / ForgeMultipart "
                f"({class_name})."
            )

    return warnings


def _recipe_dir(version: str) -> Path:
    return get_settings().minecraft_versions_path / version / "recipe"


def _export_manifest_path(version: str) -> Path:
    return _recipe_dir(version) / "_export_manifest.json"


def analyze_recipe_export_status(version: str) -> RecipeExportStatus:
    layout = recipe_layout_for_version(version)
    settings = get_settings()
    version_dir = settings.minecraft_versions_path / version
    mods_dir = version_dir / "mods"
    recipe_dir = _recipe_dir(version)

    jar_names = _list_installed_mod_jars(mods_dir)
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
            }
        )
    )

    log_path = (
        settings.minecraft_versions_path.parent
        / "recipe-exporter"
        / "versions"
        / version
        / "run"
        / "logs"
        / "latest.log"
    )
    if not log_path.is_file():
        repo_root = Path(__file__).resolve().parents[2]
        log_path = repo_root / "recipe-exporter" / "versions" / version / "run" / "logs" / "latest.log"

    log_class_errors, log_mod_errors = _parse_forge_log(log_path)
    warnings = _build_warnings(
        jar_names=jar_names,
        recipe_namespaces=recipe_namespaces,
        missing_dependencies=missing_dependencies,
        log_class_errors=log_class_errors,
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
        log_errors=tuple(log_class_errors[:10] + [f"mod:{name}" for name in log_mod_errors[:10]]),
    )


def refresh_export_manifest(version: str) -> RecipeExportStatus:
    status = analyze_recipe_export_status(version)
    manifest_path = _export_manifest_path(version)
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


def log_export_warnings(version: str) -> RecipeExportStatus:
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

    status = refresh_export_manifest(version)
    for warning in status.warnings:
        logger.warning("[recipe-export:{}] {}", version, warning)
    return status


class RecipeExportStatusService:
    def analyze(self, version: str) -> RecipeExportStatus:
        return analyze_recipe_export_status(version)

    def refresh_manifest(self, version: str) -> RecipeExportStatus:
        return refresh_export_manifest(version)

    def log_warnings(self, version: str) -> RecipeExportStatus:
        return log_export_warnings(version)


recipe_export_status_service = RecipeExportStatusService()
