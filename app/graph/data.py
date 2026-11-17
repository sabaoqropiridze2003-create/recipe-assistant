import logging

from sqlalchemy import func, or_, select

from app.db.models import DietaryProfile, PantryItem, Recipe
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