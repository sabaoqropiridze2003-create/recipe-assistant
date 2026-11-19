"""Chat with the real assistant in your terminal: real Gemini, your database and REAL MEMORY
(the Postgres checkpointer). Try: show recipes, then "what do I need to buy for the second one?".

Usage (from the project root):
    python -m scripts.try_chat <user_id>
Type quit to leave.
"""
import asyncio
import sys
import uuid

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.db.session import engine
from app.graph.builder import build_chef_graph
from app.graph.checkpoint import open_checkpointer
from app.graph.deps import make_default_deps


def ask_confirmation(info: dict) -> dict:
    """Show what is about to be saved and let the user say yes, no, or edit the list."""
    print("\n--- CONFIRMATION REQUIRED ---")
    print(f"{info['action']}: {info['title']}")
    for item in info.get("items", []):
        print(f"  - {item['quantity']} {item['unit']} {item['name']}")
    while True:
        choice = input("Save this? [y]es / [n]o / [e]dit: ").strip().lower()
        if choice in ("y", "yes"):
            return {"approved": True}
        if choice in ("n", "no"):
            return {"approved": False}
        if choice in ("e", "edit") and info.get("items"):
            print("Type one item per line as  name,quantity,unit  (empty line = done):")
            items = []
            while line := input("  > ").strip():
                name, quantity, unit = (line.split(",") + ["", ""])[:3]
                items.append({"name": name, "quantity": float(quantity or 0) or None, "unit": unit})
            return {"approved": True, "items": items}


async def main(user_id: int) -> None:
    config = {"configurable": {"thread_id": f"try-{user_id}-{uuid.uuid4().hex[:8]}"}}
    try:
        async with open_checkpointer() as checkpointer:
            graph = build_chef_graph(make_default_deps(), checkpointer)
            while True:
                text = (await asyncio.to_thread(input, "\nyou> ")).strip()
                if text.lower() in ("quit", "exit"):
                    break
                if not text:
                    continue
                result = await graph.ainvoke(
                    {"messages": [HumanMessage(content=text)], "user_id": user_id}, config
                )
                while result.get("__interrupt__"):  
                    info = result["__interrupt__"][0].value
                    reply = await asyncio.to_thread(ask_confirmation, info)
                    result = await graph.ainvoke(Command(resume=reply), config)
                print("\nassistant>", result.get("answer"))
                for number, card in enumerate(result.get("cards", []), 1):
                    tag = " [AI]" if card.get("ai_generated") else ""
                    print(f"   {number}. {card['title']}{tag} ({card['time']} min)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    user_id = int(sys.argv[1])
    if sys.platform == "win32":
        asyncio.run(main(user_id), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main(user_id))
