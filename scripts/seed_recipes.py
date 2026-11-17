"""Fill the database with the recipe catalog and index it for vector search.

Run from the project root:   python -m scripts.seed_recipes
Safe to run again: recipes that already exist are skipped, and all catalog vectors are refreshed.
Use --no-index to load the SQL data only (e.g. if the Gemini key is not set up yet).
"""
import asyncio
import sys
from collections import Counter

from sqlalchemy import select

from app.db.models import Recipe, RecipeIngredient
from app.db.session import SessionLocal, engine
from app.schemas.recipe import IngredientIn, RecipeIn
from app.services.allergens import compute_allergens
from app.services.safety import diet_claim_problems
from app.services.vector_store import index_recipes
from scripts.recipes_data import RECIPES


def to_recipe_in(raw: dict) -> RecipeIn:
    ingredients = [
        IngredientIn(
            name=item[0],
            quantity=item[1],
            unit=item[2],
            is_staple=len(item) > 3 and bool(item[3]),
        )
        for item in raw["ingredients"]
    ]
    return RecipeIn(**{**raw, "ingredients": ingredients})


async def main(index: bool) -> None:
    created = skipped = 0
    try:
        async with SessionLocal() as db:
            for raw in RECIPES:
                data = to_recipe_in(raw)  
                names = [i.name for i in data.ingredients]

                problems = diet_claim_problems(data.diet_tags, names)
                if problems:
                    raise SystemExit(f"Invalid catalog entry '{data.title}': {problems}")

                exists = await db.scalar(
                    select(Recipe.id).where(
                        Recipe.title == data.title, Recipe.source == "catalog"
                    )
                )
                if exists:
                    skipped += 1
                    continue

                recipe = Recipe(
                    title=data.title,
                    description=data.description,
                    cuisine=data.cuisine,
                    meal_type=data.meal_type,
                    servings=data.servings,
                    total_time_min=data.total_time_min,
                    steps=data.steps,
                    diet_tags=data.diet_tags,
                    allergens=compute_allergens(names),  
                    source="catalog",
                    owner_id=None,
                )
                recipe.ingredients = [
                    RecipeIngredient(
                        name=i.name, quantity=i.quantity, unit=i.unit, is_staple=i.is_staple
                    )
                    for i in data.ingredients
                ]
                db.add(recipe)
                created += 1
            await db.commit()
            print(f"Recipes: {created} created, {skipped} already existed")

            catalog = (
                await db.scalars(select(Recipe).where(Recipe.source == "catalog"))
            ).all()
            allergens = Counter(a for r in catalog for a in r.allergens)
            print(f"Catalog size: {len(catalog)} | allergens: {dict(allergens)}")

            if index:
                await index_recipes(catalog)
                print(f"Indexed {len(catalog)} recipes in the vector store")
            else:
                print("Skipped indexing (--no-index)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(index="--no-index" not in sys.argv))