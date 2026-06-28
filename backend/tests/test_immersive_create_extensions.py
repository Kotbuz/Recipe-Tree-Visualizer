from app.recipes.extensions import default_category_extensions
from app.recipes.parsers.json_recipe_parser import JsonRecipeParser


TREATED_WOOD_IE = {
    "type": "immersiveengineering:shaped_fluid",
    "category": "misc",
    "key": {
        "b": {
            "type": "immersiveengineering:fluid_stack",
            "amount": 1000,
            "tag": "c:creosote",
        },
        "w": {
            "tag": "minecraft:planks",
        },
    },
    "pattern": [
        "www",
        "wbw",
        "www",
    ],
    "result": {
        "count": 8,
        "id": "immersiveengineering:treated_wood_horizontal",
    },
}

CREATE_TREATED_WOOD = {
    "type": "create:filling",
    "ingredients": [
        {"tag": "minecraft:planks"},
        {"fluidTag": "c:creosote", "amount": 125},
    ],
    "results": [{"id": "immersiveengineering:treated_wood_horizontal"}],
}


def test_immersive_engineering_shaped_fluid_parses_treated_wood() -> None:
    parser = JsonRecipeParser()
    recipe = parser.parse(
        "immersiveengineering:crafting/treated_wood_horizontal",
        TREATED_WOOD_IE,
        source="mod:immersiveengineering",
        mod_id="immersiveengineering",
    )

    assert recipe is not None
    assert recipe.raw_type == "immersiveengineering:shaped_fluid"
    assert recipe.outputs[0].item_id == "immersiveengineering:treated_wood_horizontal"
    assert recipe.outputs[0].amount == 8.0

    input_ids = {part.item_id: part.amount for part in recipe.inputs}
    assert input_ids["tag:minecraft:planks"] == 8.0
    assert input_ids["fluid:tag:c:creosote"] == 1000.0


def test_create_filling_parses_treated_wood() -> None:
    parser = JsonRecipeParser()
    recipe = parser.parse(
        "create:filling/compat/immersiveengineering/treated_wood_in_spout",
        CREATE_TREATED_WOOD,
        source="mod:create",
        mod_id="create",
    )

    assert recipe is not None
    assert recipe.raw_type == "create:filling"
    assert recipe.outputs[0].item_id == "immersiveengineering:treated_wood_horizontal"

    input_ids = {part.item_id: part.amount for part in recipe.inputs}
    assert input_ids["tag:minecraft:planks"] == 1.0
    assert input_ids["fluid:tag:c:creosote"] == 125.0


def test_extension_display_names_include_ie_and_create() -> None:
    registry = default_category_extensions()

    assert registry.display_name("immersiveengineering:shaped_fluid") == "Immersive Engineering"
    assert registry.display_name("create:filling") == "Create Spout"
