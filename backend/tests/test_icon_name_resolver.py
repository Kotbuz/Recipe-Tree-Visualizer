from app.services.icon_name_resolver import resolve_icon_item_name


def test_resolve_planks_to_oak() -> None:
    assert resolve_icon_item_name("planks") == "oak planks"
    assert resolve_icon_item_name("Planks") == "oak planks"


def test_resolve_logs_to_oak() -> None:
    assert resolve_icon_item_name("logs") == "oak logs"
    assert resolve_icon_item_name("logs that burn") == "oak logs"


def test_resolve_stone_tool_materials_to_cobblestone() -> None:
    assert resolve_icon_item_name("stone tool materials") == "cobblestone"


def test_resolve_keeps_specific_items() -> None:
    assert resolve_icon_item_name("birch planks") == "birch planks"
    assert resolve_icon_item_name("iron block") == "iron block"
