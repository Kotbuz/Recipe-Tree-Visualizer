from enum import StrEnum


class RecipeIngredientRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    CATALYST = "catalyst"
