from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PantryItem, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.pantry import PantryCreate, PantryOut, PantryUpdate

router = APIRouter(prefix="/pantry", tags=["pantry"])


async def get_owned_item(db: AsyncSession, item_id: int, user_id: int) -> PantryItem:
    item = await db.scalar(
        select(PantryItem).where(PantryItem.id == item_id, PantryItem.user_id == user_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found")
    return item


@router.get("", response_model=list[PantryOut])
async def list_pantry(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(PantryItem).where(PantryItem.user_id == user.id).order_by(PantryItem.name)
    )
    return result.all()


@router.post("", response_model=PantryOut, status_code=status.HTTP_201_CREATED)
async def add_pantry_item(
    data: PantryCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(PantryItem).where(PantryItem.user_id == user.id, PantryItem.name == data.name)
    )
    if existing:
        if data.quantity is not None:
            if existing.quantity is not None and existing.unit != data.unit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"'{data.name}' is already stored in '{existing.unit}'. Update it with PUT instead.",
                )
            existing.quantity = (existing.quantity or 0) + data.quantity
            existing.unit = data.unit or existing.unit
        await db.commit()
        await db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return existing

    item = PantryItem(user_id=user.id, name=data.name, quantity=data.quantity, unit=data.unit)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=PantryOut)
async def update_pantry_item(
    item_id: int,
    data: PantryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await get_owned_item(db, item_id, user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an item with that name",
        )
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pantry_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await get_owned_item(db, item_id, user.id)
    await db.delete(item)
    await db.commit()