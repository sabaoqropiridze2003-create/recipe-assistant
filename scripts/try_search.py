import asyncio

from sqlalchemy import select

from app.db.models import Recipe
from app.db.session import SessionLocal, engine
from app.services.vector_store import search_similar


async def show(query, titles, recipe_ids=None):
    hits = await search_similar(query, recipe_ids=recipe_ids, k=5)
    print(f"\n{query!r}" + ("  [SQL-filtered]" if recipe_ids is not None else ""))
    for rid, distance in hits:
        print(f"  {distance:.3f}  {titles.get(rid, '?')}")


async def main():
    try:
        async with SessionLocal() as db:
            recipes = (await db.scalars(select(Recipe))).all()
        titles = {r.id: r.title for r in recipes}
        quick_ids = [r.id for r in recipes if r.total_time_min <= 20]

        await show("light vegetarian lunch with tomatoes", titles)
        await show("something with chicken and rice", titles)
        await show("a sweet dessert", titles)
        await show("ქათმის კერძი", titles)  
        await show("something with chicken and rice", titles, recipe_ids=quick_ids)
    finally:
        await engine.dispose()


asyncio.run(main())