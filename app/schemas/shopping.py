from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ShoppingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    is_bought: bool
    recipe_id: int | None


class ShoppingListSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    item_count: int


class ShoppingListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    items: list[ShoppingItemOut]


class ItemBoughtIn(BaseModel):
    is_bought: bool