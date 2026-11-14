from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DietaryProfile, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.profile import ProfileIn, ProfileOut

router = APIRouter(prefix="/profile", tags=["profile"])


async def get_or_create_profile(db: AsyncSession, user_id: int) -> DietaryProfile:
    profile = await db.get(DietaryProfile, user_id)
    if profile is None:
        profile = DietaryProfile(
            user_id=user_id,
            allergies=[],
            diet="none",
            disliked_ingredients=[],
            default_servings=2,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
async def read_profile(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await get_or_create_profile(db, user.id)


@router.put("", response_model=ProfileOut)
async def update_profile(
    data: ProfileIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_or_create_profile(db, user.id)
    profile.allergies = data.allergies
    profile.diet = data.diet
    profile.disliked_ingredients = data.disliked_ingredients
    profile.default_servings = data.default_servings
    await db.commit()
    await db.refresh(profile)
    return profile