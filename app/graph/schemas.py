from typing import Literal

from pydantic import BaseModel, Field


class Constraints(BaseModel):
    """What the user asked for in THIS message. Deliberately loose: code cleans it afterwards,
    because Gemini does not reliably enforce numeric bounds in structured output."""

    ingredients: list[str] = Field(
        default_factory=list,
        description="Ingredients the user says they have or want to use. English, lowercase, singular.",
    )
    exclude_ingredients: list[str] = Field(
        default_factory=list,
        description="Foods the user does not want in this request, in English (e.g. 'dairy', 'peanut').",
    )
    max_time_min: int | None = Field(default=None, description="Maximum total time in minutes, or null.")
    servings: int | None = Field(default=None, description="Number of servings, or null.")
    cuisine: str | None = Field(default=None, description="Cuisine in lowercase English, or null.")
    meal_type: str | None = Field(
        default=None, description="One of breakfast, lunch, dinner, snack, dessert, or null."
    )
    diet: str | None = Field(
        default=None, description="'vegetarian' or 'vegan' if requested in this message, else null."
    )
    cooking_task: str | None = Field(
        default=None,
        description="Only for cooking_help: 'scale' (change servings), 'substitute' (replace an "
        "ingredient) or 'technique' (how to cook something). Otherwise null.",
    )
    ingredient: str | None = Field(
        default=None,
        description="For a substitute request: the ingredient to replace, in English. Otherwise null.",
    )
    reference_index: int | None = Field(
        default=None,
        description="1-based position of the previously shown recipe the user means "
        "('the second one' -> 2), or null.",
    )


class RequestAnalysis(BaseModel):
    language: str = Field(
        default="English",
        description="The language the user's LAST message is written in, as an English word "
        "(English, Georgian, Spanish, ...).",
    )
    intent: Literal["find_recipe", "meal_plan", "shopping_list", "cooking_help", "off_topic"]
    constraints: Constraints = Field(default_factory=Constraints)
    refers_to_previous: bool = Field(
        default=False,
        description="True if the user refers to a recipe that was already shown (e.g. 'the second one').",
    )


class IngredientLine(BaseModel):
    name: str = Field(description="Ingredient name in English, lowercase, singular.")
    quantity: float
    unit: str = Field(description="g, ml, pcs, tbsp, tsp ...")


class RecipeDraft(BaseModel):
    """A recipe invented by the LLM. Loose on purpose: code validates and cleans it."""

    title: str
    description: str = Field(description="One or two sentences.")
    servings: int
    total_time_min: int
    ingredients: list[IngredientLine]
    steps: list[str]


class Substitutes(BaseModel):
    options: list[str] = Field(
        description="Up to 5 substitute ingredients, in English, lowercase, singular."
    )
