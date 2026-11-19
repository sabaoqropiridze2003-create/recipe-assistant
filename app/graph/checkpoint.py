"""The Postgres checkpointer: it stores the graph state of every chat between messages."""
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings


@asynccontextmanager
async def open_checkpointer():
    """Use as:  async with open_checkpointer() as checkpointer: graph = build_chef_graph(deps, checkpointer)

    setup() creates the checkpoint tables the first time and does nothing afterwards."""
    async with AsyncPostgresSaver.from_conn_string(settings.checkpoint_database_url) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
