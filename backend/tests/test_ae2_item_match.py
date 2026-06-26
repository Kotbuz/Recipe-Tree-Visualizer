from app.recipes.ae2_item_match import ae2_items_compatible


def test_base_covered_cable_matches_fluix_variant() -> None:
    base = "appliedenergistics2:item.CableCovered"
    fluix = "appliedenergistics2:item.CableCovered.Fluix"
    assert ae2_items_compatible(base, fluix)
    assert ae2_items_compatible(fluix, base)


def test_base_covered_cable_does_not_match_dye_variant() -> None:
    base = "appliedenergistics2:item.CableCovered"
    white = "appliedenergistics2:item.CableCovered.White"
    assert not ae2_items_compatible(base, white)
    assert not ae2_items_compatible(white, base)


def test_smart_cable_family_only_matches_same_type() -> None:
    covered = "appliedenergistics2:item.CableCovered.Fluix"
    smart = "appliedenergistics2:item.CableSmart.Fluix"
    assert not ae2_items_compatible(covered, smart)


def test_version_registry_matches_base_covered_to_fluix() -> None:
    from app.recipes.registry import get_version_ingredient_registry

    registry = get_version_ingredient_registry("1.7.10")
    base = "appliedenergistics2:item.CableCovered"
    fluix = "appliedenergistics2:item.CableCovered.Fluix"
    white = "appliedenergistics2:item.CableCovered.White"

    assert registry.ingredient_matches(fluix, base)
    assert registry.ingredient_matches(base, fluix)
    assert not registry.ingredient_matches(white, base)
    assert not registry.ingredient_matches(base, white)
