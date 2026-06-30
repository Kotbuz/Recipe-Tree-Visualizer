from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "java_settings.json"


@dataclass(frozen=True)
class JavaRuntimeInfo:
    major: int
    home: str
    java_executable: str
    label: str
    source: str


def _settings_path() -> Path:
    path = _SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_settings_homes() -> dict[int, str]:
    path = _settings_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    raw = payload.get("java_homes")
    if not isinstance(raw, dict):
        return {}
    homes: dict[int, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            major = int(str(key))
        except ValueError:
            continue
        homes[major] = value.strip()
    return homes


def _write_settings_homes(homes: dict[int, str]) -> None:
    path = _settings_path()
    payload = {"java_homes": {str(major): home for major, home in sorted(homes.items())}}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def java_home_from_executable(java_executable: str | Path) -> Path | None:
    path = Path(java_executable).resolve()
    if path.name.lower() not in {"java", "java.exe"}:
        return None
    if path.parent.name.lower() != "bin":
        return None
    home = path.parent.parent
    return home if home.is_dir() else None


def detect_java_major(home: Path) -> int | None:
    release = home / "release"
    if release.is_file():
        match = re.search(r'JAVA_VERSION="?(\d+)', release.read_text(encoding="utf-8", errors="replace"))
        if match:
            return int(match.group(1))

    java_bin = home / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
    if not java_bin.is_file():
        return None
    try:
        completed = subprocess.run(
            [str(java_bin), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = f"{completed.stderr}\n{completed.stdout}"
    match = re.search(r'version "(\d+)', output)
    if match:
        return int(match.group(1))
    return None


def _env_home_for_major(major: int) -> str | None:
    if major == 8:
        return os.environ.get("FORGE_JAVA_HOME") or os.environ.get("JAVA8_HOME")
    return os.environ.get(f"JAVA{major}_HOME") or (
        os.environ.get("FORGE_JAVA_HOME") if major == 8 else None
    )


def set_java_home(major: int, home: str) -> JavaRuntimeInfo:
    normalized = str(Path(home).resolve())
    home_path = Path(normalized)
    if not home_path.is_dir():
        raise ValueError(f"Папка JDK не найдена: {normalized}")

    java_executable = home_path / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
    if not java_executable.is_file():
        raise ValueError(f"java не найден: {java_executable}")

    detected_major = detect_java_major(home_path)
    if detected_major is not None and detected_major != major:
        raise ValueError(
            f"Выбранная Java {detected_major}, ожидалась Java {major}. "
            f"Укажите JDK {major} для этой версии Minecraft."
        )

    homes = _read_settings_homes()
    homes[major] = normalized
    _write_settings_homes(homes)
    return JavaRuntimeInfo(
        major=major,
        home=normalized,
        java_executable=str(java_executable),
        label=_format_label(home_path, detected_major or major),
        source="user",
    )


def clear_java_home(major: int) -> None:
    homes = _read_settings_homes()
    homes.pop(major, None)
    _write_settings_homes(homes)


def _format_label(home: Path, major: int) -> str:
    return f"Java {major} — {home.name}"


def _candidate_homes() -> list[Path]:
    candidates: list[Path] = []

    for major in (8, 17, 21, 23):
        env_home = _env_home_for_major(major)
        if env_home:
            candidates.append(Path(env_home))

    candidates.extend(Path(home) for home in _read_settings_homes().values())

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
        patterns = (
            r"C:\Program Files\Java\jdk-*",
            r"C:\Program Files\Eclipse Adoptium\jdk-*",
            r"C:\Program Files\Eclipse Adoptium\jre-*",
        )
        for pattern in patterns:
            candidates.extend(Path(path) for path in sorted(glob.glob(pattern)))

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.insert(0, Path(java_home))

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def discover_java_runtimes() -> list[JavaRuntimeInfo]:
    discovered: dict[int, JavaRuntimeInfo] = {}

    for candidate in _candidate_homes():
        if not candidate.is_dir():
            continue
        java_executable = candidate / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
        if not java_executable.is_file():
            continue
        major = detect_java_major(candidate)
        if major is None:
            continue

        source = "auto"
        settings_homes = _read_settings_homes()
        if str(candidate.resolve()) in {str(Path(v).resolve()) for v in settings_homes.values()}:
            source = "user"
        elif any(
            str(candidate.resolve()) == str(Path(env_home).resolve())
            for env_home in (_env_home_for_major(major), os.environ.get("JAVA_HOME"))
            if env_home
        ):
            source = "env"

        info = JavaRuntimeInfo(
            major=major,
            home=str(candidate.resolve()),
            java_executable=str(java_executable.resolve()),
            label=_format_label(candidate, major),
            source=source,
        )
        if major not in discovered:
            discovered[major] = info

    return [discovered[major] for major in sorted(discovered)]


def get_configured_java_homes() -> dict[int, str]:
    homes = _read_settings_homes()
    for runtime in discover_java_runtimes():
        homes.setdefault(runtime.major, runtime.home)
    return homes


def resolve_java_executable(required_major: int) -> str:
    env_home = _env_home_for_major(required_major)
    if env_home:
        java_path = Path(env_home) / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
        if java_path.is_file():
            return str(java_path)

    settings_home = _read_settings_homes().get(required_major)
    if settings_home:
        java_path = Path(settings_home) / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
        if java_path.is_file():
            return str(java_path)

    for runtime in discover_java_runtimes():
        if runtime.major == required_major:
            return runtime.java_executable

    which_java = shutil.which("java")
    if which_java:
        return which_java

    raise FileNotFoundError(
        f"Java {required_major} не найдена. Укажите JDK {required_major} в настройках Java "
        f"или задайте JAVA{required_major}_HOME / FORGE_JAVA_HOME."
    )


def pick_java_home_dialog(*, title: str = "Выберите java.exe") -> str | None:
    if sys.platform == "win32":
        return _pick_java_windows(title=title)
    return _pick_java_tkinter(title=title)


def _pick_java_tkinter(*, title: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    selected = filedialog.askopenfilename(
        title=title,
        filetypes=[("Java runtime", "java.exe"), ("All files", "*.*")],
    )
    root.destroy()
    if not selected:
        return None
    home = java_home_from_executable(selected)
    return str(home) if home else None


def _pick_java_windows(*, title: str) -> str | None:
  picked = _pick_java_tkinter(title=title)
  return picked
