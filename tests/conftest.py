"""Shared setup for the API tests (the ones marked 'integration').

They talk to the real FastAPI app and the real Postgres database, but NEVER to Gemini: the
embedding calls are replaced, and the chat graph is a fake. Every test creates its own users
with random e-mail addresses and deletes them (and what they created) at the end."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.models import Recipe, User
from app.db.session import get_db
from app.services.security import create_access_token, hash_password


@pytest.fixture
async def maker():
    """A database session factory. Skips the test if the database is not running."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)  
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("the database is not running (start it with: docker compose up -d postgres)")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(maker):
    """An HTTP client that talks to the app in-process (no server needed)."""
    from app.main import app

    async def override_get_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
async def make_user(maker):
    """Creates a user straight in the database and returns their id, e-mail and login header."""
    created: list[int] = []

    async def factory(role: str = "user") -> dict:
        email = f"test-{uuid.uuid4().hex[:12]}@example.com"
        async with maker() as db:
            user = User(email=email, full_name="Test User", hashed_password=hash_password("password123"), role=role)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        created.append(user.id)
        return {"id": user.id, "email": email, "headers": {"Authorization": f"Bearer {create_access_token(user.id)}"}}

    yield factory
    async with maker() as db:  
        await db.execute(delete(User).where(User.id.in_(created)))
        await db.commit()


@pytest.fixture
async def track_recipe(maker):
    """Remember recipes a test created, so they are deleted afterwards."""
    ids: list[int] = []
    yield ids.append
    async with maker() as db:
        await db.execute(delete(Recipe).where(Recipe.id.in_(ids)))
        await db.commit()


@pytest.fixture
def no_gemini(monkeypatch):
    """Creating or deleting a recipe normally updates the vector index (a Gemini call). Not in tests."""

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr("app.routers.recipes.index_recipe", nothing)
    monkeypatch.setattr("app.routers.recipes.remove_recipe_vector", nothing)
