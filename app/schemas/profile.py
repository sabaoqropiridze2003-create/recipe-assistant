from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.normalize import clean_list


class ProfileIn(BaseModel):
    allergies: list[str] = []
    diet: Literal["none", "vegetarian", "vegan"] = "none"
    disliked_ingredients: list[str] = []
    default_servings: int = Field(default=2, ge=1, le=20)

    @field_validator("allergies", "disliked_ingredients")
    @classmethod
    def normalize_lists(cls, v: list[str]) -> list[str]:
        return clean_list(v)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allergies: list[str]
    diet: str | None
    disliked_ingredients: list[str]
    default_servings: int