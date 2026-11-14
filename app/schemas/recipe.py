from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.normalize import clean_list, normalize_name

MealType = Literal["breakfast", "lunch", "dinner", "snack", "dessert"]
ALLOWED_DIET_TAGS = {"vegetarian", "vegan", "gluten_free"}


class IngredientIn(BaseModel):
    name: str = Field(max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    is_staple: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = normalize_name(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("unit must not be empty")
        return v


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    quantity: float
    unit: str
    is_staple: bool


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    cuisine: str | None = Field(default=None, max_length=50)
    meal_type: MealType
    servings: int = Field(ge=1, le=100)
    total_time_min: int = Field(ge=1, le=1440)
    steps: list[str] = Field(min_length=1)
    diet_tags: list[str] = []
    ingredients: list[IngredientIn] = Field(min_length=1)

    @field_validator("cuisine")
    @classmethod
    def clean_cuisine(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        return v or None

    @field_validator("steps")
    @classmethod
    def clean_steps(cls, v: list[str]) -> list[str]:
        steps = [s.strip() for s in v if s.strip()]
        if not steps:
            raise ValueError("at least one non-empty step is required")
        return steps

    @field_validator("diet_tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        tags = clean_list(v)
        unknown = [t for t in tags if t not in ALLOWED_DIET_TAGS]
        if unknown:
            raise ValueError(f"unknown diet tags: {unknown}. Allowed: {sorted(ALLOWED_DIET_TAGS)}")
        return tags


class RecipeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    cuisine: str | None
    meal_type: str
    servings: int
    total_time_min: int
    diet_tags: list[str]
    allergens: list[str]
    source: str


class RecipeOut(RecipeSummary):
    steps: list[str]
    ingredients: list[IngredientOut]
    created_at: datetime


class RecipePage(BaseModel):
    items: list[RecipeSummary]
    total: int
    page: int
    size: int


class CookbookIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class CookbookEntry(BaseModel):
    recipe: RecipeSummary
    note: str | None
    saved_at: datetime