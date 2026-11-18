"""Run the real chef graph (real Gemini + your database) once and print what happened.

Usage (from the project root):
    python -m scripts.try_chef <user_id> "your message"
    python -m scripts.try_chef <user_id> --shown 4,9 "I like the second one, make it for 6"

--shown pretends that recipes with these ids were shown in the previous message,
so you can test "the second one" before the chat memory exists (Part C).
"""
import asyncio
import sys

from langchain_core.messages import HumanMessage

from app.db.session import engine
from app.graph.builder import build_chef_graph
from app.graph.data import get_recipe
from app.graph.deps import make_default_deps


async def main(user_id: int, text: str, shown_ids: list[int]) -> None:
    graph = build_chef_graph(make_default_deps())
    try:
        last_shown = []
        for recipe_id in shown_ids:
            recipe = await get_recipe(user_id, recipe_id)
            if recipe:
                last_shown.append(
                    {"id": recipe["id"], "title": recipe["title"], "servings": recipe["servings"]}
                )
        state = await graph.ainvoke(
            {"messages": [HumanMessage(content=text)], "user_id": user_id, "last_shown": last_shown}
        )
    finally:
        await engine.dispose()

    print("intent:          ", state.get("intent"))
    print("language:        ", state.get("language"))
    print("constraints:     ", state.get("constraints"))
    print("relax attempts:  ", state.get("relax_attempts"))
    print("AI attempts:     ", state.get("generation_attempts"))
    print("hidden (safety): ", state.get("blocked_summary"))
    print("helper result:   ", state.get("helper_result"))
    if state.get("generation_attempts"):
        draft = state.get("generated_recipe") or (state.get("candidates") or [{}])[0]
        print("last AI draft:   ", draft.get("title"))
        print("why rejected:    ", state.get("generation_feedback") or "(accepted)")
    print("cards:")
    for card in state.get("cards", []):
        tag = " [AI]" if card.get("ai_generated") else ""
        print(
            f"  - {card['title']}{tag} | {card['time']} min | "
            f"missing: {card['missing']} | allergens: {card['allergens']}"
        )
    print("\nANSWER:\n" + state.get("answer", ""))


if __name__ == "__main__":
    args = sys.argv[1:]
    user_id = int(args.pop(0))
    shown: list[int] = []
    if args and args[0] == "--shown":
        args.pop(0)
        shown = [int(x) for x in args.pop(0).split(",")]
    asyncio.run(main(user_id, " ".join(args), shown))
