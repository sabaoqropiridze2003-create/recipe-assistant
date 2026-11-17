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


class RequestAnalysis(BaseModel):
    intent: Literal["find_recipe", "meal_plan", "shopping_list", "cooking_help", "off_topic"]
    constraints: Constraints = Field(default_factory=Constraints)
    refers_to_previous: bool = Field(
        default=False,
        description="True if the user refers to a recipe that was already shown (e.g. 'the second one').",
    )