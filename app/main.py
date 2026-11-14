from fastapi import FastAPI

from app.routers import auth, pantry, profile

app = FastAPI(title="Recipe Assistant")

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(pantry.router)


@app.get("/health")
async def health():
    return {"status": "ok"}