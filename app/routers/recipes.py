from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Recipe, RecipeIngredient, User
from app.db.session import get_db
from app.deps import get_current_user, require_admin
from app.schemas.recipe import RecipeIn, RecipeOut, RecipePage
from app.services.recipe_access import visible_to
from app.services.scaling import scale_quantity

from app.services.allergens import compute_allergens

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _build_ingredients(data: RecipeIn) -> list[RecipeIngredient]:
    return [
        RecipeIngredient(
            name=i.name, quantity=i.quantity, unit=i.unit, is_staple=i.is_staple
        )
        for i in data.ingredients
    ]


async def _get_catalog_recipe(db: AsyncSession, recipe_id: int) -> Recipe:
    recipe = await db.scalar(
        select(Recipe).where(Recipe.id == recipe_id, Recipe.source == "catalog")
    )
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe not found")
    return recipe


@router.get("", response_model=RecipePage)
async def list_recipes(
    cuisine: str | None = None,
    meal_type: str | None = None,
    max_time: int | None = Query(default=None, ge=1),
    diet: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = [visible_to(user.id)]
    if cuisine:
        conditions.append(func.lower(Recipe.cuisine) == cuisine.strip().lower())
    if meal_type:
        conditions.append(Recipe.meal_type == meal_type.strip().lower())
    if max_time:
        conditions.append(Recipe.total_time_min <= max_time)
    if diet:
        conditions.append(Recipe.diet_tags.any(diet.strip().lower()))
    if search:
        conditions.append(
            or_(
                Recipe.title.icontains(search, autoescape=True),
                Recipe.description.icontains(search, autoescape=True),
            )
        )

    total = await db.scalar(select(func.count()).select_from(Recipe).where(*conditions))
    result = await db.scalars(
        select(Recipe)
        .where(*conditions)
        .order_by(Recipe.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return RecipePage(items=result.all(), total=total or 0, page=page, size=size)


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(
    recipe_id: int,
    servings: int | None = Query(default=None, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.scalar(
        select(Recipe).where(Recipe.id == recipe_id, visible_to(user.id))
    )
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe not found")

    out = RecipeOut.model_validate(recipe)
    if servings is not None and servings != recipe.servings:
        for ingredient in out.ingredients:
            ingredient.quantity = scale_quantity(
                ingredient.quantity, recipe.servings, servings
            )
        out.servings = servings
    return out


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: RecipeIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = Recipe(
        title=data.title,
        description=data.description,
        cuisine=data.cuisine,
        meal_type=data.meal_type,
        servings=data.servings,
        total_time_min=data.total_time_min,
        steps=data.steps,
        diet_tags=data.diet_tags,
        allergens=compute_allergens([i.name for i in data.ingredients]),
        source="catalog",
        owner_id=None,
    )
    recipe.ingredients = _build_ingredients(data)
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    # Phase 5: index this recipe in the vector store
    return recipe


@router.put("/{recipe_id}", response_model=RecipeOut)
async def update_recipe(
    recipe_id: int,
    data: RecipeIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await _get_catalog_recipe(db, recipe_id)
    recipe.title = data.title
    recipe.description = data.description
    recipe.cuisine = data.cuisine
    recipe.meal_type = data.meal_type
    recipe.servings = data.servings
    recipe.total_time_min = data.total_time_min
    recipe.steps = data.steps
    recipe.diet_tags = data.diet_tags
    recipe.ingredients = _build_ingredients(data)  # old ones are deleted (delete-orphan)
    recipe.allergens = compute_allergens([i.name for i in data.ingredients])
    await db.commit()
    await db.refresh(recipe)
    # Phase 5: re-index this recipe
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await _get_catalog_recipe(db, recipe_id)
    await db.delete(recipe)
    await db.commit()
    # Phase 5: remove this recipe's vectors