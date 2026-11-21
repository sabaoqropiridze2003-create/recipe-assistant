"""The chat endpoints, with a FAKE graph: the real router, the real database, no Gemini."""
import json
from types import SimpleNamespace as NS

import pytest

from app.services.chat_stream import ERROR_MESSAGE
from app.services.rate_limit import RateLimiter

pytestmark = pytest.mark.integration

PENDING = {"type": "confirmation_required", "action": "save_shopping_list", "title": "List", "items": []}


class FakeGraph:
    """Replays prepared stream chunks, like the compiled LangGraph graph would."""

    def __init__(self, chunks=(), values=None, interrupts=(), crash=False):
        self.chunks = list(chunks)
        self.values = values or {}
        self.interrupts = list(interrupts)
        self.crash = crash

    async def astream(self, graph_input, config, stream_mode):
        for chunk in self.chunks:
            yield chunk
        if self.crash:
            raise RuntimeError("Gemini is down")

    async def aget_state(self, config):
        return NS(values=self.values, interrupts=self.interrupts, tasks=())


@pytest.fixture
def use_graph(maker, monkeypatch):
    """Install a fake graph in the app. The answer is saved with the test's database connection."""
    from app.main import app

    monkeypatch.setattr("app.routers.chat.SessionLocal", maker)

    def install(graph):
        app.state.graph = graph

    yield install
    app.state.graph = None


def events_of(response) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]


async def new_chat(client, user) -> int:
    return (await client.post("/chat/sessions", headers=user["headers"])).json()["id"]


async def test_a_message_is_streamed_and_both_sides_are_saved(client, make_user, use_graph):
    cards = [{"id": 5, "title": "Soup", "time": 20, "ai_generated": False}]
    use_graph(
        FakeGraph(
            chunks=[
                ("updates", {"compose_answer": {}}),
                ("messages", (NS(type="AIMessageChunk", content="Hi"), {"langgraph_node": "compose_answer"})),
            ],
            values={"answer": "Hi there", "cards": cards, "intent": "find_recipe"},
        )
    )
    alice = await make_user()
    chat_id = await new_chat(client, alice)

    response = await client.post(
        f"/chat/sessions/{chat_id}/messages", json={"content": "show me a soup"}, headers=alice["headers"]
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert [e["type"] for e in events_of(response)] == ["node", "token", "recipes", "answer", "done"]

    history = (await client.get(f"/chat/sessions/{chat_id}/messages", headers=alice["headers"])).json()
    assert [(m["role"], m["content"]) for m in history] == [("user", "show me a soup"), ("assistant", "Hi there")]
    assert history[1]["recipe_ids"] == [5]
    titles = [s["title"] for s in (await client.get("/chat/sessions", headers=alice["headers"])).json()]
    assert "show me a soup" in titles 


async def test_the_users_message_is_not_lost_when_the_graph_crashes(client, make_user, use_graph):
    use_graph(FakeGraph(crash=True))
    alice = await make_user()
    chat_id = await new_chat(client, alice)

    response = await client.post(
        f"/chat/sessions/{chat_id}/messages", json={"content": "hello"}, headers=alice["headers"]
    )
    events = events_of(response)
    assert {"type": "error", "message": ERROR_MESSAGE} in events and events[-1] == {"type": "done"}
    assert "Gemini" not in response.text  

    history = (await client.get(f"/chat/sessions/{chat_id}/messages", headers=alice["headers"])).json()
    assert [(m["role"], m["content"]) for m in history] == [("user", "hello"), ("assistant", ERROR_MESSAGE)]


async def test_a_pending_confirmation_blocks_new_messages_with_409(client, make_user, use_graph):
    use_graph(FakeGraph(interrupts=[NS(value=PENDING)]))
    alice = await make_user()
    chat_id = await new_chat(client, alice)

    blocked = await client.post(
        f"/chat/sessions/{chat_id}/messages", json={"content": "something else"}, headers=alice["headers"]
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["pending_confirmation"]["action"] == "save_shopping_list"
    assert (await client.get(f"/chat/sessions/{chat_id}/messages", headers=alice["headers"])).json() == []

    detail = (await client.get(f"/chat/sessions/{chat_id}", headers=alice["headers"])).json()
    assert detail["pending_confirmation"]["title"] == "List"  


async def test_the_confirmation_answer_is_checked_strictly(client, make_user, use_graph):
    use_graph(FakeGraph(interrupts=[NS(value=PENDING)]))
    alice = await make_user()
    chat_id = await new_chat(client, alice)
    url = f"/chat/sessions/{chat_id}/confirm"

    assert (await client.post(url, json={"approved": "yes"}, headers=alice["headers"])).status_code == 422
    assert (await client.post(url, json={"approved": True, "user_id": 99}, headers=alice["headers"])).status_code == 422
    assert (await client.post(url, json={"approved": True, "recipe": {"title": "x"}}, headers=alice["headers"])).status_code == 422

    use_graph(FakeGraph())  
    assert (await client.post(url, json={"approved": True}, headers=alice["headers"])).status_code == 409


async def test_the_rate_limit_answers_429_with_a_wait_time(client, make_user, use_graph, monkeypatch):
    monkeypatch.setattr("app.routers.chat.chat_limiter", RateLimiter(limit=1, window_seconds=3600))
    use_graph(FakeGraph(values={"answer": "ok"}))
    alice = await make_user()
    chat_id = await new_chat(client, alice)
    url = f"/chat/sessions/{chat_id}/messages"

    assert (await client.post(url, json={"content": "one"}, headers=alice["headers"])).status_code == 200
    second = await client.post(url, json={"content": "two"}, headers=alice["headers"])
    assert second.status_code == 429 and int(second.headers["Retry-After"]) > 0


async def test_blank_and_oversized_messages_are_refused(client, make_user, use_graph):
    use_graph(FakeGraph())
    alice = await make_user()
    url = f"/chat/sessions/{await new_chat(client, alice)}/messages"
    assert (await client.post(url, json={"content": "   "}, headers=alice["headers"])).status_code == 422
    assert (await client.post(url, json={"content": "x" * 1001}, headers=alice["headers"])).status_code == 422


async def test_nobody_can_write_into_someone_elses_chat(client, make_user, use_graph):
    use_graph(FakeGraph(values={"answer": "ok"}))
    alice, bob = await make_user(), await make_user()
    chat_id = await new_chat(client, alice)
    response = await client.post(
        f"/chat/sessions/{chat_id}/messages", json={"content": "hi"}, headers=bob["headers"]
    )
    assert response.status_code == 404


async def test_the_chat_says_503_when_the_graph_could_not_start(client, make_user):
    alice = await make_user()
    chat_id = await new_chat(client, alice)  
    response = await client.post(
        f"/chat/sessions/{chat_id}/messages", json={"content": "hi"}, headers=alice["headers"]
    )
    assert response.status_code == 503
