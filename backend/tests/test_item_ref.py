from app.recipes.loaders.ae2_recipe_loader import _resolve_item_token, _Ae2RecipeContext
from app.recipes.loaders.ore_dict_loader import load_ore_dict


def test_resolve_item_token_parses_trailing_metadata() -> None:
    context = _Ae2RecipeContext(version="1.7.10", ore_dict=load_ore_dict("1.7.10"))
    resolved = _resolve_item_token("ae2:BlockSkyStone:1", context)
    assert resolved == ("appliedenergistics2:tile.BlockSkyStone", 1)


def test_resolve_item_token_keeps_plain_block_metadata_none() -> None:
    context = _Ae2RecipeContext(version="1.7.10", ore_dict=load_ore_dict("1.7.10"))
    resolved = _resolve_item_token("ae2:BlockFluix", context)
    assert resolved == ("appliedenergistics2:tile.BlockFluix", None)


def test_resolve_item_part_token_maps_to_named_item() -> None:
    context = _Ae2RecipeContext(version="1.7.10", ore_dict=load_ore_dict("1.7.10"))
    resolved = _resolve_item_token("ae2:ItemPart.Interface", context)
    assert resolved == ("appliedenergistics2:item.Interface", None)
    assert _resolve_item_token("ae2:ItemPart.Terminal", context) == (
        "appliedenergistics2:item.Terminal",
        None,
    )
