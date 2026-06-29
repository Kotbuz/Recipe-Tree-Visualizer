from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_MC_VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
_MC_VERSION_IN_PATH_RE = re.compile(r"(?<![\d.])\d+\.\d+(?:\.\d+)?(?![\d.])")
_FORGE_LEGACY_BUILD_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_FORGE_MODERN_BUILD_RE = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
_FORGE_LOADER_ID_RE = re.compile(
    r"^forge[-:]?(?P<build>\d+\.\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ModpackVersionInfo:
    minecraft_version: str
    modpack_name: str | None = None
    loader: str | None = None
    forge_version: str | None = None
    detection_source: str = "unknown"


class ModpackVersionUndetectedError(Exception):
    pass


def normalize_minecraft_version(raw: str) -> str | None:
    candidate = raw.strip()
    if _MC_VERSION_RE.match(candidate):
        return candidate
    match = _MC_VERSION_IN_PATH_RE.search(candidate)
    if match:
        return match.group(0)
    return None


def normalize_forge_build(raw: str) -> str | None:
    candidate = raw.strip()
    if _FORGE_LEGACY_BUILD_RE.match(candidate) or _FORGE_MODERN_BUILD_RE.match(candidate):
        return candidate
    return extract_forge_build_from_installer_version(candidate)


def extract_forge_build_from_installer_version(raw: str) -> str | None:
    stripped = raw.strip()
    modern = re.match(
        r"^\d+\.\d+(?:\.\d+)?-(?P<build>\d+\.\d+\.\d+(?:\.\d+)?)$",
        stripped,
    )
    if modern:
        build = modern.group("build")
        if _FORGE_LEGACY_BUILD_RE.match(build) or _FORGE_MODERN_BUILD_RE.match(build):
            return build
    match = re.search(
        r"(?<=\-)(?P<build>\d+\.\d+\.\d+\.\d+)(?:\-|$)",
        stripped,
    )
    if match and _FORGE_LEGACY_BUILD_RE.match(match.group("build")):
        return match.group("build")
    return None


def forge_installer_version(mc_version: str, forge_build: str) -> str:
    if mc_version.startswith("1.7"):
        return f"{mc_version}-{forge_build}-{mc_version}"
    return f"{mc_version}-{forge_build}"


def parse_forge_loader_id(loader_id: str) -> tuple[str, str | None]:
    stripped = loader_id.strip()
    if not stripped:
        return "forge", None
    match = _FORGE_LOADER_ID_RE.match(stripped)
    if match:
        return "forge", match.group("build")
    lowered = stripped.lower()
    if lowered.startswith("forge"):
        return "forge", None
    return stripped.split("-", 1)[0], None


def detect_modpack_version_from_zip(archive_path: Path) -> ModpackVersionInfo | None:
    if not archive_path.is_file():
        return None
    try:
        with zipfile.ZipFile(archive_path) as archive:
            return _detect_from_zip_archive(archive)
    except zipfile.BadZipFile:
        return None


def find_modpack_metadata_root(source_path: Path) -> Path:
    """Корень инстанса Prism/CF: mmc-pack.json, libraries/ и т.д."""
    resolved = source_path.expanduser().resolve()
    if not resolved.is_dir():
        return resolved

    markers = (
        "mmc-pack.json",
        "minecraftinstance.json",
        "manifest.json",
        "instance.cfg",
    )
    for candidate in [resolved, *list(resolved.parents)[:6]]:
        if any((candidate / marker).is_file() for marker in markers):
            return candidate
        forge_libs = candidate / "libraries" / "net" / "minecraftforge" / "forge"
        if forge_libs.is_dir():
            return candidate
    return resolved


def detect_modpack_version_from_directory(source_path: Path) -> ModpackVersionInfo | None:
    resolved = source_path.expanduser().resolve()
    if not resolved.is_dir():
        return None

    metadata_root = find_modpack_metadata_root(resolved)
    info = _detect_from_metadata_files(metadata_root)
    if info is None and metadata_root != resolved:
        info = _detect_from_metadata_files(resolved)
    if info is not None:
        return _enrich_with_forge_from_libraries(info, metadata_root)

    for jar_path in sorted(resolved.rglob("*.jar")):
        if jar_path.parent.name == "mods" or "mods" in jar_path.parts:
            version = _guess_version_from_jar_name(jar_path.name)
            if version is not None:
                return ModpackVersionInfo(
                    minecraft_version=version,
                    detection_source="jar_filename",
                )

    for mods_dir in _iter_mods_dirs(resolved):
        version = _detect_version_from_mods_tree(mods_dir)
        if version is not None:
            return ModpackVersionInfo(
                minecraft_version=version,
                detection_source="mods_tree",
            )

    folder_version = normalize_minecraft_version(resolved.name)
    if folder_version is not None:
        return ModpackVersionInfo(
            minecraft_version=folder_version,
            detection_source="folder_name",
        )
    return None


def _detect_from_metadata_files(root: Path) -> ModpackVersionInfo | None:
    for relative in (
        "manifest.json",
        "minecraftinstance.json",
        "mmc-pack.json",
        "modpack.yml",
        "instance.cfg",
        "version.json",
    ):
        candidate = root / relative
        if not candidate.is_file():
            continue
        info = _detect_from_file(candidate)
        if info is not None:
            return info
    return None


def _detect_from_zip_archive(archive: zipfile.ZipFile) -> ModpackVersionInfo | None:
    names = archive.namelist()
    for member in (
        "manifest.json",
        "minecraftinstance.json",
        "mmc-pack.json",
        "modpack.yml",
        "instance.cfg",
        "version.json",
    ):
        if member not in names:
            continue
        try:
            payload = archive.read(member)
        except KeyError:
            continue
        info = _parse_payload(member, payload)
        if info is not None:
            return _enrich_with_forge_from_zip_paths(info, names)

    forge_build = detect_forge_from_library_paths(names)
    mc_version = _detect_version_from_zip_paths(names)
    if forge_build is not None and mc_version is not None:
        return ModpackVersionInfo(
            minecraft_version=mc_version,
            loader="forge",
            forge_version=forge_build,
            detection_source="zip_libraries",
        )

    for member in names:
        pure = PurePosixPath(member)
        if pure.suffix.lower() != ".jar":
            continue
        if pure.parts[0] != "mods" and "mods" not in pure.parts:
            continue
        version = _guess_version_from_jar_name(pure.name)
        if version is not None:
            return ModpackVersionInfo(
                minecraft_version=version,
                detection_source="jar_filename",
            )

    version = _detect_version_from_zip_paths(names)
    if version is not None:
        info = ModpackVersionInfo(
            minecraft_version=version,
            detection_source="zip_path",
        )
        return _enrich_with_forge_from_zip_paths(info, names)
    return None


def _detect_from_file(path: Path) -> ModpackVersionInfo | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    return _parse_payload(path.name, payload)


def _parse_payload(filename: str, payload: bytes) -> ModpackVersionInfo | None:
    lowered = filename.lower()
    if lowered.endswith(".json"):
        return _parse_json_manifest(payload, filename)
    if lowered.endswith(".yml") or lowered.endswith(".yaml"):
        return _parse_modpack_yml(payload)
    if lowered == "instance.cfg":
        return _parse_instance_cfg(payload)
    return None


def _parse_json_manifest(payload: bytes, filename: str) -> ModpackVersionInfo | None:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    if filename.lower() == "manifest.json":
        return _parse_curseforge_manifest(data)
    if filename.lower() == "minecraftinstance.json":
        return _parse_minecraft_instance_json(data)
    if filename.lower() == "mmc-pack.json":
        return _parse_mmc_pack(data)
    if filename.lower() == "version.json":
        return _parse_version_json(data)
    return None


def _parse_curseforge_manifest(data: dict[str, object]) -> ModpackVersionInfo | None:
    minecraft = data.get("minecraft")
    if not isinstance(minecraft, dict):
        return None
    raw_version = minecraft.get("version")
    if not isinstance(raw_version, str):
        return None
    version = normalize_minecraft_version(raw_version)
    if version is None:
        return None

    loader: str | None = None
    forge_version: str | None = None
    loaders = minecraft.get("modLoaders")
    if isinstance(loaders, list):
        for entry in loaders:
            if not isinstance(entry, dict):
                continue
            loader_id = entry.get("id")
            if isinstance(loader_id, str) and loader_id:
                loader, forge_version = parse_forge_loader_id(loader_id)
                break

    name = data.get("name")
    modpack_name = name if isinstance(name, str) else None
    return ModpackVersionInfo(
        minecraft_version=version,
        modpack_name=modpack_name,
        loader=loader,
        forge_version=forge_version,
        detection_source="manifest.json",
    )


def _parse_minecraft_instance_json(data: dict[str, object]) -> ModpackVersionInfo | None:
    base_loader = data.get("baseModLoader")
    version: str | None = None
    loader: str | None = None
    forge_version: str | None = None
    if isinstance(base_loader, dict):
        raw_mc = base_loader.get("minecraftVersion")
        if isinstance(raw_mc, str):
            version = normalize_minecraft_version(raw_mc)
        raw_loader_version = base_loader.get("version")
        if isinstance(raw_loader_version, str):
            mc_from_loader = normalize_minecraft_version(raw_loader_version)
            if mc_from_loader:
                version = mc_from_loader
            else:
                forge_version = normalize_forge_build(raw_loader_version)
        raw_loader = base_loader.get("name") or base_loader.get("type")
        if isinstance(raw_loader, str):
            loader = raw_loader.lower() if raw_loader.isalpha() else str(raw_loader)
        raw_forge = base_loader.get("forgeVersion") or base_loader.get("loaderVersion")
        if isinstance(raw_forge, str):
            forge_version = normalize_forge_build(raw_forge) or forge_version

    if version is None:
        raw_game = data.get("gameVersion")
        if isinstance(raw_game, str):
            version = normalize_minecraft_version(raw_game)

    if version is None:
        return None

    name = data.get("name")
    modpack_name = name if isinstance(name, str) else None
    return ModpackVersionInfo(
        minecraft_version=version,
        modpack_name=modpack_name,
        loader=loader or ("forge" if forge_version else None),
        forge_version=forge_version,
        detection_source="minecraftinstance.json",
    )


def _parse_mmc_pack(data: dict[str, object]) -> ModpackVersionInfo | None:
    components = data.get("components")
    if not isinstance(components, list):
        return None

    mc_version: str | None = None
    forge_version: str | None = None
    loader: str | None = None

    for entry in components:
        if not isinstance(entry, dict):
            continue
        uid = entry.get("uid")
        if not isinstance(uid, str):
            continue
        component_version = entry.get("version")
        cached_version = entry.get("cachedVersion")
        version_raw = component_version if isinstance(component_version, str) else None
        cached_raw = cached_version if isinstance(cached_version, str) else None

        if uid == "net.minecraft":
            for raw in (version_raw, cached_raw):
                if raw:
                    mc_version = normalize_minecraft_version(raw)
                    if mc_version:
                        break
        elif uid == "net.minecraftforge":
            loader = "forge"
            for raw in (version_raw, cached_raw):
                if raw:
                    forge_version = normalize_forge_build(raw)
                    if forge_version:
                        break

    if mc_version is None:
        return None

    return ModpackVersionInfo(
        minecraft_version=mc_version,
        loader=loader,
        forge_version=forge_version,
        detection_source="mmc-pack.json",
    )


def _parse_version_json(data: dict[str, object]) -> ModpackVersionInfo | None:
    for key in ("id", "minecraftVersion", "version"):
        raw = data.get(key)
        if isinstance(raw, str):
            version = normalize_minecraft_version(raw)
            if version is not None:
                return ModpackVersionInfo(
                    minecraft_version=version,
                    detection_source="version.json",
                )
    return None


def _parse_modpack_yml(payload: bytes) -> ModpackVersionInfo | None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None

    version: str | None = None
    name: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            version = normalize_minecraft_version(stripped.split(":", 1)[1].strip().strip("'\""))
        elif stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip().strip("'\"")
    if version is None:
        return None
    return ModpackVersionInfo(
        minecraft_version=version,
        modpack_name=name,
        detection_source="modpack.yml",
    )


def _parse_instance_cfg(payload: bytes) -> ModpackVersionInfo | None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None

    for line in text.splitlines():
        if not line.startswith("MCVersion="):
            continue
        version = normalize_minecraft_version(line.split("=", 1)[1].strip())
        if version is not None:
            return ModpackVersionInfo(
                minecraft_version=version,
                detection_source="instance.cfg",
            )
    return None


def _detect_version_from_zip_paths(names: list[str]) -> str | None:
    counts: dict[str, int] = {}
    for member in names:
        pure = PurePosixPath(member)
        for part in pure.parts:
            version = normalize_minecraft_version(part)
            if version is not None and part in {"mods", "config", "scripts", "overrides"}:
                continue
            if version is not None:
                counts[version] = counts.get(version, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def _iter_mods_dirs(root: Path):
    direct = root / "mods"
    if direct.is_dir():
        yield direct
    prism = root / "minecraft" / "mods"
    if prism.is_dir():
        yield prism
    overrides = root / "overrides" / "mods"
    if overrides.is_dir():
        yield overrides


def _detect_version_from_mods_tree(mods_dir: Path) -> str | None:
    for child in mods_dir.iterdir():
        if child.is_dir():
            version = normalize_minecraft_version(child.name)
            if version is not None:
                return version
    return None


def _guess_version_from_jar_name(filename: str) -> str | None:
    lowered = filename.lower()
    match = re.search(r"-(\d+\.\d+(?:\.\d+)?)-", lowered)
    if match:
        return normalize_minecraft_version(match.group(1))
    match = re.search(r"-(\d+\.\d+(?:\.\d+)?)(?:-|$)", lowered)
    if match:
        return normalize_minecraft_version(match.group(1))
    return None


def detect_forge_from_library_paths(paths: list[str] | tuple[str, ...]) -> str | None:
    """Из путей вида libraries/net/minecraftforge/forge/<version>/…"""
    prefix = "libraries/net/minecraftforge/forge/"
    builds: list[str] = []
    for raw in paths:
        normalized = raw.replace("\\", "/").lstrip("./")
        if not normalized.startswith(prefix):
            continue
        version_part = normalized[len(prefix) :].split("/", 1)[0]
        build = normalize_forge_build(version_part) or extract_forge_build_from_installer_version(
            version_part
        )
        if build:
            builds.append(build)
    if not builds:
        return None
    return builds[-1]


def detect_forge_from_instance_libraries(root: Path) -> str | None:
    forge_lib = root / "libraries" / "net" / "minecraftforge" / "forge"
    if not forge_lib.is_dir():
        return None

    builds: list[str] = []
    for version_dir in sorted(forge_lib.iterdir()):
        if not version_dir.is_dir():
            continue
        build = normalize_forge_build(version_dir.name)
        if build:
            builds.append(build)
            continue
        build = extract_forge_build_from_installer_version(version_dir.name)
        if build:
            builds.append(build)

    if not builds:
        return None
    return builds[-1]


def _enrich_with_forge_from_zip_paths(
    info: ModpackVersionInfo,
    names: list[str],
) -> ModpackVersionInfo:
    if info.forge_version is not None:
        return info
    forge_build = detect_forge_from_library_paths(names)
    if forge_build is None:
        return info
    return ModpackVersionInfo(
        minecraft_version=info.minecraft_version,
        modpack_name=info.modpack_name,
        loader=info.loader or "forge",
        forge_version=forge_build,
        detection_source=f"{info.detection_source}+zip_libraries",
    )


def _enrich_with_forge_from_libraries(
    info: ModpackVersionInfo,
    root: Path,
) -> ModpackVersionInfo:
    if info.forge_version is not None:
        return info
    forge_build = detect_forge_from_instance_libraries(root)
    if forge_build is None:
        return info
    return ModpackVersionInfo(
        minecraft_version=info.minecraft_version,
        modpack_name=info.modpack_name,
        loader=info.loader or "forge",
        forge_version=forge_build,
        detection_source=f"{info.detection_source}+libraries",
    )


_FORGE_VERSION_REQUIREMENT = re.compile(
    r"^\s*Forge\s*:\s*\[(?P<version>[^\],)]+)",
    re.MULTILINE,
)


def infer_forge_build_from_crash_reports(minecraft_version: str) -> str | None:
    from app.core.config import get_settings

    settings = get_settings()
    repo_root = settings.minecraft_versions_path.parent
    if not repo_root.is_dir():
        repo_root = Path(__file__).resolve().parents[2]

    crash_dirs = [
        repo_root / "recipe-exporter" / "forge-runtime" / minecraft_version / "crash-reports",
    ]
    for crash_dir in crash_dirs:
        if not crash_dir.is_dir():
            continue
        reports = sorted(
            crash_dir.glob("crash-*.txt"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for report in reports[:3]:
            text = report.read_text(encoding="utf-8", errors="replace")
            match = _FORGE_VERSION_REQUIREMENT.search(text)
            if match:
                return normalize_forge_build(match.group("version").strip())
    return None
