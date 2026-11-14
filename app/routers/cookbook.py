from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Recipe, SavedRecipe, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.recipe import CookbookEntry, CookbookIn, RecipeSummary
from app.services.recipe_access import visible_to

router = APIRouter(prefix="/cookbook", tags=["cookbook"])


@router.get("", response_model=list[CookbookEntry])
async def list_cookbook(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await db.execute(
        select(SavedRecipe, Recipe)
        .join(Recipe, Recipe.id == SavedRecipe.recipe_id)
        .where(SavedRecipe.user_id == user.id)
        .order_by(SavedRecipe.saved_at.desc())
    )
    return [
        CookbookEntry(
            recipe=RecipeSummary.model_validate(recipe),
            note=saved.note,
            saved_at=saved.saved_at,
        )
        for saved, recipe in rows.all()
    ]


@router.post("/{recipe_id}", response_model=CookbookEntry, status_code=status.HTTP_201_CREATED)
async def save_recipe(
    recipe_id: int,
    response: Response,
    data: CookbookIn | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.scalar(
        select(Recipe).where(Recipe.id == recipe_id, visible_to(user.id))
    )
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe not found")

    saved = await db.get(SavedRecipe, (user.id, recipe_id))
    if saved:
        if data and data.note is not None:
            saved.note = data.note
        response.status_code = status.HTTP_200_OK
    else:
        saved = SavedRecipe(
            user_id=user.id, recipe_id=recipe_id, note=data.note if data else None
        )
        db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return CookbookEntry(
        recipe=RecipeSummary.model_validate(recipe),
        note=saved.note,
        saved_at=saved.saved_at,
    )


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recipe(
    recipe_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    saved = await db.get(SavedRecipe, (user.id, recipe_id))
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe is not in your cookbook")
    await db.delete(saved)
    await db.commit()