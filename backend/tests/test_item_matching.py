from app.services.item_matching import (
    display_name_matches,
    item_id_path_matches,
    items_match,
)


def test_item_id_path_matches_distinguishes_flint_variants() -> None:
    assert item_id_path_matches("flint", "minecraft:flint")
    assert not item_id_path_matches("flint", "minecraft:flint_and_steel")


def test_display_name_matches_is_exact() -> None:
    assert display_name_matches("flint", "flint")
    assert not display_name_matches("flint", "flint and steel")


def test_items_match_suffix_patterns() -> None:
    assert items_match("oak planks", "minecraft oak planks")
    assert not items_match("flint", "flint and steel")
