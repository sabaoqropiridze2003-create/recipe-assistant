from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShoppingList, ShoppingListItem, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.shopping import (
    ItemBoughtIn,
    ShoppingItemOut,
    ShoppingListOut,
    ShoppingListSummary,
)

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])


async def _get_owned_list(db: AsyncSession, list_id: int, user_id: int) -> ShoppingList:
    shopping_list = await db.scalar(
        select(ShoppingList).where(
            ShoppingList.id == list_id, ShoppingList.user_id == user_id
        )
    )
    if shopping_list is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shopping list not found")
    return shopping_list


@router.get("", response_model=list[ShoppingListSummary])
async def list_shopping_lists(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id)
        .order_by(ShoppingList.created_at.desc())
    )
    return [
        ShoppingListSummary(
            id=sl.id, title=sl.title, created_at=sl.created_at, item_count=len(sl.items)
        )
        for sl in result.all()
    ]


@router.get("/{list_id}", response_model=ShoppingListOut)
async def get_shopping_list(
    list_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_list(db, list_id, user.id)


@router.patch("/{list_id}/items/{item_id}", response_model=ShoppingItemOut)
async def mark_item(
    list_id: int,
    item_id: int,
    data: ItemBoughtIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(
        select(ShoppingListItem)
        .join(ShoppingList, ShoppingList.id == ShoppingListItem.list_id)
        .where(
            ShoppingListItem.id == item_id,
            ShoppingListItem.list_id == list_id,
            ShoppingList.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    item.is_bought = data.is_bought
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(
    list_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    shopping_list = await _get_owned_list(db, list_id, user.id)
    await db.delete(shopping_list)
    await db.commit()