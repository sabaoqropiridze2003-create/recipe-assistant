import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request

from app.graph.builder import build_chef_graph
from app.graph.checkpoint import open_checkpointer
from app.graph.deps import make_default_deps
from app.routers import analytics, auth, chat, cookbook, pantry, profile, recipes, shopping_lists

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the chat graph once at startup. If that fails, the rest of the API still works
    and the chat endpoints answer 503, with the reason in the log."""
    app.state.graph = None
    app.state.checkpointer = None
    async with AsyncExitStack() as stack:
        try:
            checkpointer = await stack.enter_async_context(open_checkpointer())
            app.state.checkpointer = checkpointer
            app.state.graph = build_chef_graph(make_default_deps(), checkpointer)
            logger.info("chat graph is ready")
        except Exception:
            logger.exception(
                "The chat graph could not start. Common causes: GOOGLE_API_KEY is missing, the database "
                "is not running, or (on Windows) the server runs without --reload and psycopg cannot "
                "use the default event loop."
            )
        yield


app = FastAPI(title="Recipe Assistant", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(pantry.router)
app.include_router(recipes.router)
app.include_router(cookbook.router)
app.include_router(shopping_lists.router)
app.include_router(chat.router)
app.include_router(analytics.router)


@app.get("/health")
async def health(request: Request):
    return {"status": "ok", "chat": request.app.state.graph is not None}
