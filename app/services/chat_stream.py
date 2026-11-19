"""Turns one run of the chef graph into a stream of small events for the browser (SSE).

Nothing in this file knows about HTTP or the database, so it can be tested with a fake graph."""
import json
import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


TOKEN_NODES = {"compose_answer", "polite_refusal"}
ERROR_MESSAGE = "Sorry, something went wrong while I was thinking. Your message was saved, please try again."


def format_sse(event: dict) -> str:
    """One Server-Sent Event: a line starting with 'data: ' and a blank line after it."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def chunk_text(content) -> str:
    """A streamed chunk may hold a string or a list of parts."""
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") == "text":
            parts.append(part.get("text", ""))
    return "".join(parts)


def pending_interrupts(snapshot) -> list:
    """The questions the graph is waiting for an answer to (empty if it is not waiting)."""
    direct = getattr(snapshot, "interrupts", None)
    if direct:
        return list(direct)
    return [i for task in getattr(snapshot, "tasks", ()) or () for i in getattr(task, "interrupts", ()) or ()]


async def stream_turn(graph, graph_input, config, result: dict) -> AsyncIterator[dict]:
    """Run the graph and yield events. `result` is filled in for the caller, which saves the answer
    to the database BEFORE sending the final 'done' event."""
    try:
        async for mode, data in graph.astream(graph_input, config, stream_mode=["updates", "messages"]):
            if mode == "updates":
                for node_name in data:
                    if node_name != "__interrupt__":
                        yield {"type": "node", "name": node_name}
            elif mode == "messages":
                chunk, metadata = data
                if metadata.get("langgraph_node") in TOKEN_NODES and getattr(chunk, "type", "") == "AIMessageChunk":
                    text = chunk_text(chunk.content)
                    if text:
                        yield {"type": "token", "content": text}

        snapshot = await graph.aget_state(config)
        pending = pending_interrupts(snapshot)
        if pending:
            result["pending"] = pending[0].value
            yield {"type": "confirmation_required", **pending[0].value}
            return

        values = snapshot.values or {}
        cards = values.get("cards") or []
        answer = values.get("answer") or ""
        result.update(
            answer=answer,
            cards=cards,
            intent=values.get("intent"),
            ai_generated=any(card.get("ai_generated") for card in cards),
        )
        if cards:
            yield {"type": "recipes", "items": cards}
        yield {"type": "answer", "content": answer}
    except Exception:
        logger.exception("chat run failed")
        result.update(error=True, answer=ERROR_MESSAGE, cards=[], intent="error", ai_generated=False)
        yield {"type": "error", "message": ERROR_MESSAGE}
