import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ChatMessage, ChatSession, User
from app.db.session import SessionLocal, get_db
from app.deps import get_current_user
from app.schemas.chat import (
    ConfirmIn,
    MessageOut,
    SendMessageIn,
    SessionDetail,
    SessionOut,
)
from app.services.chat_stream import format_sse, pending_interrupts, stream_turn
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


chat_limiter = RateLimiter(limit=settings.chat_messages_per_hour, window_seconds=3600)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def get_graph(request: Request):
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The chat is not available right now. Check the server log for the reason.",
        )
    return graph


def thread_config(session: ChatSession, request: Request) -> dict:
    """One chat session = one LangGraph thread. Both ids are decided here on the server.
    tags/metadata make the trace easy to find in LangSmith (no email, token or password in them)."""
    config: dict = {
        "configurable": {"thread_id": f"chat-{session.id}"},
        "tags": ["recipe-assistant", settings.environment],
        "metadata": {"session_id": session.id, "environment": settings.environment},
    }
    tracer = getattr(request.app.state, "tracer", None)
    if tracer is not None:
        config["callbacks"] = [tracer]
    return config


async def _owned_session(db: AsyncSession, session_id: int, user_id: int) -> ChatSession:
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    if session is None:  
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return session


async def _save_assistant_message(session_id: int, result: dict) -> None:
    """The answer is saved with its own database session: the request's session may be closed."""
    if not result.get("answer"):
        return
    try:
        async with SessionLocal() as db:
            db.add(
                ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=result["answer"],
                    recipe_ids=[c["id"] for c in result.get("cards", []) if c.get("id") is not None],
                    intent=result.get("intent"),
                    ai_generated=bool(result.get("ai_generated")),
                )
            )
            session = await db.get(ChatSession, session_id)
            if session:
                session.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        logger.exception("could not save the assistant message of chat %s", session_id)


def _stream_response(graph, graph_input, config: dict, session_id: int) -> StreamingResponse:
    async def events():
        result: dict = {}
        async for event in stream_turn(graph, graph_input, config, result):
            yield format_sse(event)
        await _save_assistant_message(session_id, result)
        yield format_sse({"type": "done"})

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


# ------------------------------------------------------------------ sessions
@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return rows.all()


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph=Depends(get_graph),
):
    """Also tells the UI whether the assistant is waiting for a confirmation (e.g. after a page reload)."""
    session = await _owned_session(db, session_id, user.id)
    pending = pending_interrupts(await graph.aget_state(thread_config(session, request)))
    detail = SessionDetail.model_validate(session)
    detail.pending_confirmation = pending[0].value if pending else None
    return detail


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_session(db, session_id, user.id)
    rows = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id)
        .limit(limit)
    )
    return rows.all()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _owned_session(db, session_id, user.id)
    config = thread_config(session, request)
    await db.delete(session)  
    await db.commit()
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if checkpointer is not None: 
        try:
            await checkpointer.adelete_thread(config["configurable"]["thread_id"])
        except Exception:
            logger.warning("could not delete the checkpoints of chat %s", session_id, exc_info=True)


# ------------------------------------------------------------------ messages (streamed)
@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    body: SendMessageIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph=Depends(get_graph),
):
    session = await _owned_session(db, session_id, user.id)
    config = thread_config(session, request)

    pending = pending_interrupts(await graph.aget_state(config))
    if pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": "Please answer the pending confirmation first.",
                "pending_confirmation": pending[0].value,
            },
        )

    allowed, retry_after = chat_limiter.check(user.id)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many messages. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    db.add(ChatMessage(session_id=session.id, role="user", content=body.content))
    if session.title == "New chat":
        session.title = body.content[:50]
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    graph_input = {"messages": [HumanMessage(content=body.content)], "user_id": user.id}
    return _stream_response(graph, graph_input, config, session.id)


@router.post("/sessions/{session_id}/confirm")
async def confirm(
    session_id: int,
    body: ConfirmIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph=Depends(get_graph),
):
    session = await _owned_session(db, session_id, user.id)
    config = thread_config(session, request)

    if not pending_interrupts(await graph.aget_state(config)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing is waiting for a confirmation.")

    answer: dict = {"approved": body.approved}
    if body.items is not None:
        answer["items"] = [item.model_dump() for item in body.items]
    return _stream_response(graph, Command(resume=answer), config, session.id)
