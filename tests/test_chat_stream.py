import json
from types import SimpleNamespace as NS

from app.services.chat_stream import (
    ERROR_MESSAGE,
    chunk_text,
    format_sse,
    pending_interrupts,
    stream_turn,
)


class FakeGraph:
    """Pretends to be the compiled graph: it replays prepared stream chunks."""

    def __init__(self, chunks, values=None, interrupts=(), crash=False):
        self.chunks = chunks
        self.values = values or {}
        self.interrupts = list(interrupts)
        self.crash = crash

    async def astream(self, graph_input, config, stream_mode):
        assert stream_mode == ["updates", "messages"]
        for chunk in self.chunks:
            yield chunk
        if self.crash:
            raise RuntimeError("Gemini is down")

    async def aget_state(self, config):
        return NS(values=self.values, interrupts=self.interrupts, tasks=())


def token(text, node="compose_answer"):
    return ("messages", (NS(type="AIMessageChunk", content=text), {"langgraph_node": node}))


async def collect(graph):
    result: dict = {}
    events = [event async for event in stream_turn(graph, {}, {}, result)]
    return events, result


async def test_tokens_come_only_from_the_writing_nodes_and_only_as_chunks():
    chunks = [
        ("updates", {"understand_request": {}}),
        token('{"intent": "find_recipe"}', node="understand_request"),
        ("updates", {"compose_answer": {}}),
        token("Hel"),
        token("lo"),
        ("messages", (NS(type="ai", content="Hello"), {"langgraph_node": "compose_answer"})), 
    ]
    events, _ = await collect(FakeGraph(chunks, values={"answer": "Hello"}))
    assert [e["content"] for e in events if e["type"] == "token"] == ["Hel", "lo"]


async def test_node_events_skip_the_interrupt_marker():
    chunks = [("updates", {"search_recipes": {}}), ("updates", {"__interrupt__": ("x",)})]
    events, _ = await collect(FakeGraph(chunks, values={"answer": "ok"}))
    assert [e["name"] for e in events if e["type"] == "node"] == ["search_recipes"]


async def test_a_finished_turn_sends_recipes_then_the_final_answer():
    cards = [{"id": 5, "title": "Soup", "time": 20, "ai_generated": False}]
    values = {"answer": "Try the soup.", "cards": cards, "intent": "find_recipe"}
    events, result = await collect(FakeGraph([token("Try")], values=values))
    assert [e["type"] for e in events] == ["token", "recipes", "answer"]
    assert events[-1]["content"] == "Try the soup."  
    assert result == {"answer": "Try the soup.", "cards": cards, "intent": "find_recipe", "ai_generated": False}


async def test_an_ai_recipe_is_flagged_for_the_statistics():
    cards = [{"id": None, "title": "Pudding", "time": 10, "ai_generated": True}]
    _, result = await collect(FakeGraph([], values={"answer": "New recipe", "cards": cards}))
    assert result["ai_generated"] is True


async def test_a_waiting_confirmation_is_sent_instead_of_an_answer():
    question = {"type": "confirmation_required", "action": "save_shopping_list", "title": "List", "items": []}
    graph = FakeGraph([("updates", {"confirm_action": {}})], interrupts=[NS(value=question)])
    events, result = await collect(graph)
    assert events[-1] == question
    assert not any(e["type"] == "answer" for e in events)
    assert result == {"pending": question}  


async def test_a_crash_becomes_a_friendly_error_event():
    events, result = await collect(FakeGraph([("updates", {"search_recipes": {}})], crash=True))
    assert events[-1] == {"type": "error", "message": ERROR_MESSAGE}
    assert result["error"] is True and result["answer"] == ERROR_MESSAGE
    assert "Gemini" not in json.dumps(events)  


def test_chunk_text_handles_strings_and_parts():
    assert chunk_text("abc") == "abc"
    assert chunk_text([{"type": "text", "text": "a"}, "b", {"type": "image"}]) == "ab"
    assert chunk_text(None) == ""


def test_sse_format_keeps_georgian_readable():
    line = format_sse({"type": "token", "content": "გამარჯობა"})
    assert line == 'data: {"type": "token", "content": "გამარჯობა"}\n\n'


def test_pending_interrupts_understands_both_snapshot_shapes():
    one = NS(value="q")
    assert pending_interrupts(NS(interrupts=[one], tasks=())) == [one]
    assert pending_interrupts(NS(interrupts=(), tasks=[NS(interrupts=[one])])) == [one]
    assert pending_interrupts(NS(interrupts=(), tasks=())) == []
