from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionOut):
    pending_confirmation: dict | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    recipe_ids: list[int]
    created_at: datetime


class SendMessageIn(BaseModel):
    content: str = Field(max_length=1000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class ConfirmItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: StrictBool  
    items: list[ConfirmItem] | None = Field(default=None, max_length=100)
