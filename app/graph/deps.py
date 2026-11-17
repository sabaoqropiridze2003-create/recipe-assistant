from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol


class ChefLLM(Protocol):
    """Everything the graph needs from a language model. The real one talks to Gemini;
    tests pass a fake one with canned answers."""

    async def analyze(self, history: list[tuple[str, str]]) -> dict: ...

    async def compose(self, payload: dict) -> str: ...


@dataclass
class ChefDeps:
    llm: ChefLLM
    load_context: Callable[[int], Awaitable[tuple[dict, list[str]]]]
    search: Callable[[int, dict, str], Awaitable[list[dict]]]


def make_default_deps() -> ChefDeps:
    """The real thing: Gemini + the database. Imported lazily so tests never need them."""
    from app.graph.data import load_context, search_candidates
    from app.graph.llm import GeminiChefLLM

    return ChefDeps(llm=GeminiChefLLM(), load_context=load_context, search=search_candidates)