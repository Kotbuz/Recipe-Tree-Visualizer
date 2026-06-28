"""Generate bundled tag snapshots from vanilla jar + NeoForge universal jar."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from app.core.config import get_settings
from app.recipes.loaders.tag_loader import TagLoader

NEOFORGE_URLS: dict[str, str] = {
    "1.21.1": "https://maven.neoforged.net/releases/net/neoforged/neoforge/21.1.89/neoforge-21.1.89-universal.jar",
}

# Common modpack tags not shipped in NeoForge core (gears/rods/plates from ore mods).
CURATED_EXTENSIONS: dict[str, dict[str, list[str]]] = {
    "1.21.1": {
        "tag:c:gears/stone": ["minecraft:flint"],
        "tag:c:gears/copper": ["minecraft:copper_ingot"],
        "tag:c:gears/aluminum": ["alltheores:aluminum_gear"],
        "tag:c:gears/steel": ["alltheores:steel_gear"],
        "tag:c:gears/gold": ["alltheores:gold_gear"],
        "tag:c:gears/enderium": ["alltheores:enderium_gear"],
        "tag:c:gears/zinc": ["alltheores:zinc_gear"],
        "tag:c:gears/desh": ["alltheores:desh_gear"],
        "tag:c:gears/iridium": ["alltheores:iridium_gear"],
        "tag:c:rods/copper": ["alltheores:copper_rod"],
        "tag:c:rods/nickel": ["alltheores:nickel_rod"],
        "tag:c:rods/osmium": ["alltheores:osmium_rod"],
        "tag:c:rods/stone": ["minecraft:stick"],
        "tag:c:plates/copper": ["alltheores:copper_plate"],
        "tag:c:plates/silver": ["alltheores:silver_plate"],
        "tag:c:plates/diamond": ["alltheores:diamond_plate"],
        "tag:c:plates/steel": ["alltheores:steel_plate"],
        "tag:c:storage_blocks/bronze": ["alltheores:bronze_block"],
        "tag:c:storage_blocks/black_quartz": ["actuallyadditions:black_quartz_block"],
        "tag:c:leathers": ["minecraft:leather"],
        "tag:c:immersiveengineering:treated_wood": ["immersiveengineering:treated_wood_horizontal"],
    },
}


def _download_jar(url: str, destination: Path) -> None:
    destination.write_bytes(urllib.request.urlopen(url, timeout=120).read())


def build_snapshot(version: str) -> dict[str, list[str]]:
    loader = TagLoader()
    versions_root = get_settings().minecraft_versions_path
    vanilla_jar = versions_root / version / "client.jar"
    if not vanilla_jar.is_file():
        raise FileNotFoundError(f"Vanilla jar not found: {vanilla_jar}")

    tag_maps = [loader.load_from_jar(vanilla_jar)]

    neo_url = NEOFORGE_URLS.get(version)
    if neo_url:
        neo_jar = Path(f"_neoforge-{version}.jar")
        try:
            _download_jar(neo_url, neo_jar)
            tag_maps.append(loader.load_from_jar(neo_jar))
        finally:
            neo_jar.unlink(missing_ok=True)

    merged = loader.merge_tag_maps(*tag_maps)

    curated = CURATED_EXTENSIONS.get(version, {})
    for tag_id, members in curated.items():
        merged = loader.merge_tag_maps(
            merged,
            {tag_id: frozenset(members)},
        )

    snapshot: dict[str, list[str]] = {}
    for tag_id in sorted(merged):
        if not tag_id.startswith("tag:c:"):
            continue
        resolved = sorted(
            member
            for member in loader.resolve_transitive(merged, tag_id)
            if not member.startswith("#") and not member.startswith("tag:")
        )
        if resolved:
            snapshot[tag_id] = resolved

    for tag_id, members in curated.items():
        existing = set(snapshot.get(tag_id, []))
        existing.update(members)
        if existing:
            snapshot[tag_id] = sorted(existing)

    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", default="1.21.1")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "tag_snapshots",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(args.version)
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / f"{args.version}.json"
    output_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(snapshot)} c: tags to {output_path}")


if __name__ == "__main__":
    main()
