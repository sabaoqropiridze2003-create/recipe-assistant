"""Run the real chef graph (real Gemini + your database) once and print what happened.

Usage (from the project root):
    python -m scripts.try_chef <user_id> "your message"
"""
import asyncio
import sys

from langchain_core.messages import HumanMessage

from app.db.session import engine
from app.graph.builder import build_chef_graph
from app.graph.deps import make_default_deps


async def main(user_id: int, text: str) -> None:
    graph = build_chef_graph(make_default_deps())
    try:
        state = await graph.ainvoke(
            {"messages": [HumanMessage(content=text)], "user_id": user_id}
        )
    finally:
        await engine.dispose()

    print("intent:         ", state.get("intent"))
    print("constraints:    ", state.get("constraints"))
    print("relax attempts: ", state.get("relax_attempts"))
    print("hidden (safety):", state.get("blocked_summary"))
    print("cards:")
    for card in state.get("cards", []):
        print(
            f"  - {card['title']} | {card['time']} min | "
            f"missing: {card['missing']} | allergens: {card['allergens']}"
        )
    print("\nANSWER:\n" + state.get("answer", ""))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), " ".join(sys.argv[2:])))