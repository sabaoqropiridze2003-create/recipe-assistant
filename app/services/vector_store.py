import asyncio

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

from app.config import settings

COLLECTION_NAME = "recipes"
_store: PGVector | None = None


def get_vector_store() -> PGVector:
    """Create the vector store once and reuse it."""
    global _store
    if _store is None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in .env")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            google_api_key=settings.google_api_key,
        )
        _store = PGVector(
            embeddings=embeddings,
            collection_name=COLLECTION_NAME,
            connection=settings.vector_database_url,
            use_jsonb=True,
        )
    return _store


def recipe_to_text(recipe) -> str:
    """The text that gets embedded: one recipe = one vector."""
    ingredients = ", ".join(i.name for i in recipe.ingredients)
    parts = [
        recipe.title,
        recipe.description,
        f"Ingredients: {ingredients}",
        f"Meal: {recipe.meal_type}",
    ]
    if recipe.cuisine:
        parts.append(f"Cuisine: {recipe.cuisine}")
    if recipe.diet_tags:
        parts.append(f"Tags: {', '.join(recipe.diet_tags)}")
    return ". ".join(p for p in parts if p)


def recipe_to_document(recipe) -> Document:
    return Document(page_content=recipe_to_text(recipe), metadata={"recipe_id": recipe.id})


async def index_recipes(recipes) -> None:
    """Add or overwrite vectors. Using the recipe id as the vector id makes this idempotent."""
    recipes = list(recipes)
    if not recipes:
        return
    docs = [recipe_to_document(r) for r in recipes]
    ids = [str(r.id) for r in recipes]
    await asyncio.to_thread(get_vector_store().add_documents, docs, ids=ids)


async def index_recipe(recipe) -> None:
    await index_recipes([recipe])


async def remove_recipe_vector(recipe_id: int) -> None:
    await asyncio.to_thread(get_vector_store().delete, ids=[str(recipe_id)])


async def search_similar(
    query: str, *, recipe_ids: list[int] | None = None, k: int = 20
) -> list[tuple[int, float]]:
    """Rank recipes by meaning. If recipe_ids is given, only those recipes are considered
    (they come from the strict SQL filters). Returns (recipe_id, distance); lower = closer."""
    if recipe_ids is not None and not recipe_ids:
        return []
    metadata_filter = {"recipe_id": {"$in": recipe_ids}} if recipe_ids is not None else None
    results = await asyncio.to_thread(
        get_vector_store().similarity_search_with_score, query, k=k, filter=metadata_filter
    )
    return [(int(doc.metadata["recipe_id"]), float(score)) for doc, score in results]