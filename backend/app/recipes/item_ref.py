from __future__ import annotations


def split_trailing_metadata(value: str) -> tuple[str, int | None]:
    if ":" not in value:
        return value, None

    base, suffix = value.rsplit(":", 1)
    if suffix.isdigit():
        return base, int(suffix)
    return value, None


def parse_item_needle(needle: str, explicit_metadata: int | None = None) -> tuple[str, int | None]:
    cleaned = needle.strip()
    if not cleaned:
        return "", explicit_metadata

    if explicit_metadata is not None:
        base, _ = split_trailing_metadata(cleaned)
        return base, explicit_metadata

    return split_trailing_metadata(cleaned)


def normalize_item_ref(item_id: str, metadata: int | None) -> tuple[str, int | None]:
    if metadata is not None:
        return item_id, metadata

    base, trailing_meta = split_trailing_metadata(item_id)
    if trailing_meta is None:
        return item_id, metadata
    return base, trailing_meta
