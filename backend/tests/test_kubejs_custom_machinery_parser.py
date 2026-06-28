from __future__ import annotations

from app.recipes.providers.kubejs_custom_machinery_parser import parse_custom_machinery_script

RECYCLING_SNIPPET = """
ServerEvents.recipes(event => {
    function fluidRecycler(fluid, output, time, id) {
        event.recipes.custommachinery.custom_machine("techopolis:fluid_recycler", time)
            .requireFluid(fluid)
            .produceItem(output)
            .id(id)
    }

    fluidRecycler("10000x immersiveengineering:creosote", "techopolis:fluid_recycling_coupon", 100, 'techopolis:fluid_recycler/creosote')
})
"""

MINER_SNIPPET = """
ServerEvents.recipes(event => {
    function basicMiner(resource, count, time) {
        event.recipes.custommachinery.custom_machine("techopolis:basic_miner", time)
            .requireStructure([["a"]], { "a": resource })
            .produceItem(Item.of(resource, count))
    }

    basicMiner("minecraft:cobblestone", 2, 100)
})
"""

ALLOY_KILN_SNIPPET = """
ServerEvents.recipes(event => {
    function alloyKilnRecipes(input1, input2, input3, output, energy, time, id) {
        let recipe = event.recipes.custommachinery.custom_machine("techopolis:alloy_kiln", time)
            .requireStructure([["a"]], { "a": "techopolis:wooden_scaffolding" })
        recipe.requireItem(input1)
        recipe.requireItem(input2)
        recipe.produceItem(output)
        recipe.id(id)
    }

    alloyKilnRecipes('3x minecraft:copper_ingot', 'alltheores:tin_ingot', null, '4x alltheores:bronze_ingot', null, 200, 'techopolis:alloy_kiln/bronze')
})
"""

TECHNIUM_SNIPPET = """
ServerEvents.recipes(event => {
    event.recipes.custommachinery.custom_machine("techopolis:basic_technium_machine", 200)
        .requireStructure([["a"]], { "a": "techopolis:wooden_scaffolding" })
        .requireItem("4x #c:gears/stone")
        .produceItem("techopolis:basic_technium_ingot")
        .id('techopolis:basic_technium_ingot_cm')
})
"""


def test_parse_fluid_recycler_helper() -> None:
    recipes = parse_custom_machinery_script(RECYCLING_SNIPPET, source_file="Recycling.js")
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.id == "techopolis:fluid_recycler/creosote"
    assert recipe.catalyst_id == "techopolis:fluid_recycler"
    assert recipe.duration_ticks == 100
    assert recipe.raw_type == "custommachinery:custom_machine"
    assert recipe.inputs[0].item_id == "fluid:immersiveengineering:creosote"
    assert recipe.inputs[0].amount == 10000.0
    assert recipe.outputs[0].item_id == "techopolis:fluid_recycling_coupon"


def test_parse_miner_item_of_output() -> None:
    recipes = parse_custom_machinery_script(MINER_SNIPPET, source_file="Miners.js")
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.catalyst_id == "techopolis:basic_miner"
    assert recipe.outputs[0].item_id == "minecraft:cobblestone"
    assert recipe.outputs[0].amount == 2.0
    assert recipe.inputs == []


def test_parse_alloy_kiln_recipe_variable_methods() -> None:
    recipes = parse_custom_machinery_script(ALLOY_KILN_SNIPPET, source_file="AlloyKiln.js")
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.id == "techopolis:alloy_kiln/bronze"
    assert [io.item_id for io in recipe.inputs] == [
        "minecraft:copper_ingot",
        "alltheores:tin_ingot",
    ]
    assert recipe.inputs[0].amount == 3.0
    assert recipe.outputs[0].item_id == "alltheores:bronze_ingot"
    assert recipe.outputs[0].amount == 4.0


def test_parse_inline_technium_recipe_with_structure() -> None:
    recipes = parse_custom_machinery_script(TECHNIUM_SNIPPET, source_file="TechniumMachines.js")
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.id == "techopolis:basic_technium_ingot_cm"
    assert recipe.inputs[0].item_id == "tag:c:gears/stone"
    assert recipe.inputs[0].amount == 4.0
    assert recipe.outputs[0].item_id == "techopolis:basic_technium_ingot"
