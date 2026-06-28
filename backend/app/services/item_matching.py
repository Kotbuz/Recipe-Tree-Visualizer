def items_match(required_name: str, candidate_name: str) -> bool:
    if not required_name or not candidate_name:
        return False

    required = required_name.lower()
    candidate = candidate_name.lower()

    if required == candidate:
        return True
    if candidate.endswith(f" {required}"):
        return True
    return required.endswith(f" {candidate}")


def item_id_path_matches(needle: str, item_id: str) -> bool:
    """Сопоставление по id предмета без ложных срабатываний (flint ≠ flint_and_steel)."""
    normalized = item_id.strip().lower()
    needle = needle.strip().lower()
    if not needle or not normalized:
        return False

    if items_match(needle, normalized):
        return True

    path = normalized.split(":", 1)[-1]
    if items_match(needle, path):
        return True
    if needle.replace(" ", "_") == path:
        return True

    if ":" in needle:
        needle_path = needle.split(":", 1)[-1]
        return items_match(needle_path, path) or needle_path.replace(" ", "_") == path

    return False


def display_name_matches(needle: str, display_name: str) -> bool:
    """Точное совпадение отображаемого имени (flint ≠ flint and steel)."""
    if not needle or not display_name:
        return False
    return items_match(needle.strip().lower(), display_name.strip().lower())


_QUARTZ_DUST_TAG_KEYS = frozenset(
    {
        "tag:ae2:all_quartz_dust",
        "ae2:all_quartz_dust",
        "all quartz dust",
        "tag:c:dusts/quartz",
        "c:dusts/quartz",
        "tag:c:dusts/certus_quartz",
        "c:dusts/certus_quartz",
    }
)


def looks_like_quartz_dust_ref(value: str) -> bool:
    normalized = value.strip().lower().removeprefix("tag:")
    if not normalized:
        return False

    path = normalized.split(":", 1)[1] if ":" in normalized else normalized
    if "quartz" not in path or "dust" not in path:
        return False
    if any(token in path for token in ("glass", "fiber", "bud", "ore")):
        return False
    return True


def quartz_dust_tag_lookup_keys() -> frozenset[str]:
    return _QUARTZ_DUST_TAG_KEYS


def quartz_dust_tags_compatible(needle: str, tag_id: str) -> bool:
    if not looks_like_quartz_dust_ref(needle):
        return False
    normalized_tag = tag_id.strip().lower()
    if normalized_tag in _QUARTZ_DUST_TAG_KEYS:
        return True
    without_prefix = normalized_tag.removeprefix("tag:")
    return any(
        fragment in without_prefix
        for fragment in ("all_quartz_dust", "dusts/quartz", "dusts/certus_quartz")
    )
