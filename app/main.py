from fastapi import FastAPI

from app.routers import auth, cookbook, pantry, profile, recipes, shopping_lists

app = FastAPI(title="Recipe Assistant")

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(pantry.router)
app.include_router(recipes.router)
app.include_router(cookbook.router)
app.include_router(shopping_lists.router)


@app.get("/health")
async def health():
    return {"status": "ok"}