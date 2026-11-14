from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.normalize import normalize_name


def _clean_unit(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().lower()
    return v or None


class PantryCreate(BaseModel):
    name: str = Field(max_length=100)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = normalize_name(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str | None) -> str | None:
        return _clean_unit(v)


class PantryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = normalize_name(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str | None) -> str | None:
        return _clean_unit(v)


class PantryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    added_at: datetime