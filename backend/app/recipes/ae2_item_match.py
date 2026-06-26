from __future__ import annotations

_AE2_MOD = "appliedenergistics2"
_AE2_CABLE_FAMILIES = frozenset(
    {"CableGlass", "CableCovered", "CableSmart", "CableDense", "CableAnchor"}
)
_AE2_MATERIAL_VARIANTS = frozenset({"Fluix", "Quartz"})
_AE2_PAINT_FAMILIES = frozenset({"PaintBall", "LumenPaintBall"})


def ae2_item_family_parts(item_id: str) -> tuple[str, str | None] | None:
    normalized = item_id.strip().lower()
    prefix = f"{_AE2_MOD}:item."
    if not normalized.startswith(prefix):
        return None

    rest = normalized.removeprefix(prefix)
    if rest in {family.lower() for family in _AE2_CABLE_FAMILIES}:
        for family in _AE2_CABLE_FAMILIES:
            if rest == family.lower():
                return family, None

    family_name, _, variant = rest.partition(".")
    canonical_family = next(
        (family for family in _AE2_CABLE_FAMILIES if family.lower() == family_name),
        None,
    )
    if canonical_family is not None:
        return canonical_family, variant or None
    if family_name in {family.lower() for family in _AE2_PAINT_FAMILIES}:
        canonical_paint = next(
            family for family in _AE2_PAINT_FAMILIES if family.lower() == family_name
        )
        return canonical_paint, variant or None
    return None


def ae2_items_compatible(required_id: str, candidate_id: str) -> bool:
    required = ae2_item_family_parts(required_id)
    candidate = ae2_item_family_parts(candidate_id)
    if required is None or candidate is None:
        return False

    required_family, required_variant = required
    candidate_family, candidate_variant = candidate
    if required_family != candidate_family:
        return False

    if required_family in _AE2_CABLE_FAMILIES:
        return _ae2_cable_variants_compatible(required_variant, candidate_variant)

    if required_family in _AE2_PAINT_FAMILIES:
        if required_variant is None or candidate_variant is None:
            return required_variant == candidate_variant
        return required_variant == candidate_variant

    return False


def _ae2_cable_variants_compatible(
    required_variant: str | None,
    candidate_variant: str | None,
) -> bool:
    if required_variant is not None:
        required_variant = _canonical_material_variant(required_variant)
    if candidate_variant is not None:
        candidate_variant = _canonical_material_variant(candidate_variant)

    if required_variant == candidate_variant:
        return True
    if (
        required_variant is not None
        and candidate_variant is not None
        and required_variant.lower() == candidate_variant.lower()
    ):
        return True

    # AE2 recipes often use ae2:CableCovered without suffix; in-game that is Fluix.
    if required_variant is None:
        return candidate_variant in _AE2_MATERIAL_VARIANTS
    if candidate_variant is None:
        return required_variant in _AE2_MATERIAL_VARIANTS

    return False


def _canonical_material_variant(variant: str) -> str:
    for material in _AE2_MATERIAL_VARIANTS:
        if variant.lower() == material.lower():
            return material
    return variant
