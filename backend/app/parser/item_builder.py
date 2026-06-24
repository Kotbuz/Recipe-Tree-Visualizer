from app.schemas.domain import Item


def build_item(item_id: str, mod_id: str, texture_paths: list[str]) -> Item:
    return Item(
        id=item_id,
        name=display_name(item_id),
        icon=resolve_icon(item_id, mod_id, texture_paths),
        mod_id=mod_id,
    )


def display_name(item_id: str) -> str:
    raw = item_id.split(":", maxsplit=1)[-1]
    if raw.startswith("tag:"):
        raw = raw.removeprefix("tag:")
    return raw.replace("_", " ").title()


def resolve_icon(item_id: str, mod_id: str, texture_paths: list[str]) -> str:
    if item_id.startswith("tag:"):
        return f"tag:{item_id.removeprefix('tag:')}"

    namespace, _, path = item_id.partition(":")
    item_name = path or namespace
    if namespace != mod_id:
        return item_id

    prefix = f"assets/{mod_id}/textures/item/{item_name}"
    for texture_path in texture_paths:
        if texture_path.startswith(prefix):
            return texture_path

    return f"assets/{mod_id}/textures/item/{item_name}.png"
