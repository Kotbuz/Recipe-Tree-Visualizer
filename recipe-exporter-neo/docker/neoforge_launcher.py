#!/usr/bin/env python3
"""Launch NeoForge dedicated server from a Prism/MultiMC instance and export recipes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _log(message: str) -> None:
    print(f"[neo-launcher] {message}", flush=True)


def find_instance_root(path: Path) -> Path:
    markers = ("mmc-pack.json", "minecraftinstance.json", "manifest.json", "instance.cfg")
    resolved = path.resolve()
    for candidate in [resolved, *list(resolved.parents)[:6]]:
        if any((candidate / marker).is_file() for marker in markers):
            return candidate
    return resolved


def resolve_minecraft_dir(instance_root: Path) -> Path:
    nested = instance_root / "minecraft"
    if nested.is_dir() and (nested / "mods").is_dir():
        return nested
    if (instance_root / "mods").is_dir():
        return instance_root
    return nested if nested.is_dir() else instance_root


def read_loader_version(instance_root: Path, fallback: str) -> str:
    mmc = instance_root / "mmc-pack.json"
    if mmc.is_file():
        payload = json.loads(mmc.read_text(encoding="utf-8"))
        components = payload.get("components")
        if isinstance(components, list):
            for entry in components:
                if not isinstance(entry, dict):
                    continue
                uid = str(entry.get("uid", "")).lower()
                version = entry.get("version")
                if uid in {"net.neoforged", "net.neoforged.neoforge", "net.neoforged.forge"}:
                    if isinstance(version, str) and version.strip():
                        return version.strip()
    return fallback.strip()


def find_unix_args(instance_root: Path, loader_version: str) -> Path:
    candidates = [
        instance_root
        / "libraries"
        / "net"
        / "neoforged"
        / "neoforge"
        / loader_version
        / "unix_args.txt",
        instance_root
        / "libraries"
        / "net"
        / "neoforged"
        / "forge"
        / loader_version
        / "unix_args.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"unix_args.txt not found for NeoForge {loader_version} under {instance_root / 'libraries'}"
    )


def sync_instance(instance_root: Path, minecraft_dir: Path, work_dir: Path) -> Path:
    work_minecraft = work_dir / "minecraft"
    if work_minecraft.exists():
        shutil.rmtree(work_minecraft)
    shutil.copytree(
        minecraft_dir,
        work_minecraft,
        ignore=shutil.ignore_patterns("logs", "crash-reports", "saves", "backups"),
    )

    for name in ("libraries", "versions", "assets", "runtime"):
        src = instance_root / name
        dst = work_dir / name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.log"))

    return work_minecraft


def ensure_server_props(minecraft_dir: Path) -> None:
    props = minecraft_dir / "server.properties"
    if not props.is_file():
        props.write_text("online-mode=false\n", encoding="utf-8")
        return
    lines = props.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    found = False
    for line in lines:
        if line.startswith("online-mode="):
            updated.append("online-mode=false")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append("online-mode=false")
    props.write_text("\n".join(updated) + "\n", encoding="utf-8")


def ensure_eula(minecraft_dir: Path) -> None:
    eula = minecraft_dir / "eula.txt"
    eula.write_text("eula=true\n", encoding="utf-8")


def install_exporter_mod(minecraft_dir: Path, exporter_jar: Path) -> None:
    mods_dir = minecraft_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    for existing in mods_dir.glob("rtv-recipe-exporter-neo*.jar"):
        existing.unlink()
    shutil.copy2(exporter_jar, mods_dir / exporter_jar.name)


def main() -> int:
    instance_path = Path(os.environ["INSTANCE_PATH"])
    output_dir = Path(os.environ["OUTPUT_DIR"])
    loader_version = os.environ.get("LOADER_VERSION", "").strip()
    minecraft_version = os.environ.get("MINECRAFT_VERSION", "1.21.1").strip()
    java_xmx = os.environ.get("NEOFORGE_JAVA_XMX", "8G")
    exporter_jar = Path(
        os.environ.get(
            "EXPORTER_MOD_JAR",
            "/opt/rtv-recipe-exporter-neo/baked-mods/rtv-recipe-exporter-neo.jar",
        )
    )

    if not instance_path.is_dir():
        _log(f"Instance path not found: {instance_path}")
        return 1
    if not exporter_jar.is_file():
        _log(f"Exporter mod jar missing: {exporter_jar}")
        return 1

    instance_root = find_instance_root(instance_path)
    minecraft_dir = resolve_minecraft_dir(instance_root)
    loader_version = read_loader_version(instance_root, loader_version)
    unix_args = find_unix_args(instance_root, loader_version)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "export-server.log"

    with tempfile.TemporaryDirectory(prefix="rtv-neo-export-") as tmp:
        work_dir = Path(tmp)
        work_minecraft = sync_instance(instance_root, minecraft_dir, work_dir)
        ensure_eula(work_minecraft)
        ensure_server_props(work_minecraft)
        install_exporter_mod(work_minecraft, exporter_jar)

        export_dir = output_dir.as_posix()
        jvm_props = [
            f"-Xmx{java_xmx}",
            "-Djava.awt.headless=true",
            "-Drtv.recipe.export=true",
            f"-Drtv.recipe.export.dir={export_dir}",
            f"-Drtv.recipe.export.minecraft={minecraft_version}",
            f"-Drtv.recipe.export.loader={loader_version}",
        ]

        java_bin = os.environ.get("JAVA_HOME", "")
        java_cmd = str(Path(java_bin) / "bin" / "java") if java_bin else "java"

        command = [java_cmd, *jvm_props, f"@{unix_args}", "nogui"]
        _log(f"Instance root: {instance_root}")
        _log(f"Minecraft dir: {work_minecraft}")
        _log(f"NeoForge: {loader_version}")
        _log(f"Output: {output_dir}")
        _log(f"Command: {' '.join(command[:6])} ... nogui")

        with log_file.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=work_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            exit_code = process.wait()

    if exit_code != 0:
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-4000:] if log_file.is_file() else ""
        _log(f"Server exited with code {exit_code}")
        if tail:
            print(tail, file=sys.stderr)
        return exit_code

    snapshot = output_dir / "recipes.baked.json"
    if not snapshot.is_file():
        _log("Export finished but recipes.baked.json was not created")
        return 2

    _log("Export completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
