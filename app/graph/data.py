"""Database access for the graph. Each function opens its own short session."""
import logging

from sqlalchemy import func, or_, select

from app.db.models import (
    DietaryProfile,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SavedRecipe,
    ShoppingList,
    ShoppingListItem,
)
from app.db.session import SessionLocal
from app.services.recipe_access import visible_to
from app.services.vector_store import search_similar

logger = logging.getLogger(__name__)


async def load_context(user_id: int) -> tuple[dict, list[str]]:
    async with SessionLocal() as db:
        profile = await db.get(DietaryProfile, user_id)
        names = await db.scalars(
            select(PantryItem.name).where(
                PantryItem.user_id == user_id,
                or_(PantryItem.quantity.is_(None), PantryItem.quantity > 0),
            )
        )
        pantry = list(names.all())

    profile_dict = {
        "allergies": list(profile.allergies) if profile else [],
        "diet": profile.diet if profile else "none",
        "disliked_ingredients": list(profile.disliked_ingredients) if profile else [],
        "default_servings": profile.default_servings if profile else 2,
    }
    return profile_dict, pantry


def _recipe_to_dict(recipe: Recipe) -> dict:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "description": recipe.description,
        "cuisine": recipe.cuisine,
        "meal_type": recipe.meal_type,
        "servings": recipe.servings,
        "total_time_min": recipe.total_time_min,
        "diet_tags": list(recipe.diet_tags),
        "allergens": list(recipe.allergens),
        "source": recipe.source,
        "ingredients": [
            {"name": i.name, "quantity": i.quantity, "unit": i.unit, "is_staple": i.is_staple}
            for i in recipe.ingredients
        ],
    }


async def search_candidates(user_id: int, constraints: dict, query: str) -> list[dict]:
    """Hybrid search: strict rules in SQL first, then rank the survivors by meaning."""
    conditions = [visible_to(user_id)]
    if constraints.get("max_time_min"):
        conditions.append(Recipe.total_time_min <= constraints["max_time_min"])
    if constraints.get("meal_type"):
        conditions.append(Recipe.meal_type == constraints["meal_type"])
    if constraints.get("cuisine"):
        conditions.append(func.lower(Recipe.cuisine) == constraints["cuisine"])

    async with SessionLocal() as db:
        recipes = (await db.scalars(select(Recipe).where(*conditions))).all()
        items = [_recipe_to_dict(r) for r in recipes]
    if not items:
        return []

    distances: dict[int, float] = {}
    try:
        ranked = await search_similar(query, recipe_ids=[i["id"] for i in items], k=20)
        distances = dict(ranked)
    except Exception:
        logger.warning("vector search failed, falling back to SQL results only", exc_info=True)

    if distances:
        items = [i for i in items if i["id"] in distances]
    for item in items:
        item["distance"] = distances.get(item["id"])
    return items


async def get_recipe(user_id: int, recipe_id: int) -> dict | None:
    """One recipe, but only if this user is allowed to see it."""
    async with SessionLocal() as db:
        recipe = await db.scalar(
            select(Recipe).where(Recipe.id == recipe_id, visible_to(user_id))
        )
        return _recipe_to_dict(recipe) if recipe else None


async def get_pantry(user_id: int) -> list[dict]:
    """The pantry WITH quantities (load_context only needs the names)."""
    async with SessionLocal() as db:
        rows = await db.scalars(select(PantryItem).where(PantryItem.user_id == user_id))
        return [{"name": r.name, "quantity": r.quantity, "unit": r.unit} for r in rows.all()]


async def save_shopping_list(user_id: int, title: str, items: list[dict]) -> int:
    """Only called AFTER the user confirmed. user_id comes from the server, never from the client."""
    async with SessionLocal() as db:
        shopping_list = ShoppingList(user_id=user_id, title=title[:255])
        shopping_list.items = [
            ShoppingListItem(
                name=i["name"],
                quantity=i.get("quantity"),
                unit=i.get("unit"),
                recipe_id=i.get("recipe_id"),
            )
            for i in items
        ]
        db.add(shopping_list)
        await db.commit()
        await db.refresh(shopping_list)
        return shopping_list.id


async def save_recipe_to_cookbook(user_id: int, recipe: dict) -> int:
    """Only called AFTER the user confirmed. A catalog recipe is just added to the cookbook.
    An AI recipe is first stored as a private recipe (source 'ai_generated') and then added."""
    async with SessionLocal() as db:
        recipe_id = recipe.get("id")
        if recipe_id is None:
            existing = await db.scalar(
                select(Recipe.id).where(
                    Recipe.owner_id == user_id,
                    Recipe.source == "ai_generated",
                    Recipe.title == recipe["title"],
                )
            )
            if existing:
                recipe_id = existing
            else:
                row = Recipe(
                    title=recipe["title"],
                    description=recipe.get("description", ""),
                    cuisine=recipe.get("cuisine"),
                    meal_type=recipe.get("meal_type") or "dinner",
                    servings=recipe["servings"],
                    total_time_min=recipe["total_time_min"],
                    steps=recipe.get("steps", []),
                    diet_tags=recipe.get("diet_tags", []),
                    allergens=recipe.get("allergens", []),
                    source="ai_generated",
                    owner_id=user_id,
                )
                row.ingredients = [
                    RecipeIngredient(
                        name=i["name"],
                        quantity=i["quantity"],
                        unit=i["unit"],
                        is_staple=i.get("is_staple", False),
                    )
                    for i in recipe["ingredients"]
                ]
                db.add(row)
                await db.flush()  
                recipe_id = row.id
        else:
            visible = await db.scalar(
                select(Recipe.id).where(Recipe.id == recipe_id, visible_to(user_id))
            )
            if visible is None:
                raise ValueError("recipe not found")

        if await db.get(SavedRecipe, (user_id, recipe_id)) is None:
            db.add(SavedRecipe(user_id=user_id, recipe_id=recipe_id))
        await db.commit()
        return recipe_id
