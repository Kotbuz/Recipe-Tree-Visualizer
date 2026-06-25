from pathlib import Path

from app.indexer.mod_summary import build_mod_summary
from app.parser.jar_reader import JarReader
from app.recipes.providers.mod_jar import ModJarProvider
from app.services.item_service import item_service
from app.services.mod_service import mod_service

NATURES_COMPASS_JAR = Path(__file__).parent / "fixtures" / "NaturesCompass-26.2-3.3.0-neoforge.jar"


def test_build_mod_summary_counts_recipes_and_items() -> None:
    raw = JarReader().read(str(NATURES_COMPASS_JAR))
    result = ModJarProvider().load(str(NATURES_COMPASS_JAR))
    summary = build_mod_summary(raw, result)

    assert summary.mod_id == "naturescompass"
    assert summary.recipe_count == 2
    assert summary.skipped_recipe_count == 0
    assert summary.item_count > 0
    assert summary.machine_count > 0


def test_mod_upload_registers_summary_only() -> None:
    summary = mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)])[0]

    assert summary.mod_id == "naturescompass"
    assert summary.recipe_count == 2
    assert mod_service.list_mods()[0].mod_id == "naturescompass"


def test_mod_items_searchable_via_ingredient_registry() -> None:
    mod_service.upload_mods_from_paths([str(NATURES_COMPASS_JAR)])

    items = item_service.search_items("naturescompass", version="26.2")
    assert any(item.id == "naturescompass:naturescompass" for item in items.items)
