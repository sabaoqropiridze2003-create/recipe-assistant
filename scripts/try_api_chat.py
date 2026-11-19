"""Talk to the RUNNING API the way the Streamlit UI will: log in, open a chat, send messages,
watch the streamed events, and answer confirmations.

Start the server first (uvicorn app.main:app --reload), then, in a second terminal:
    python -m scripts.try_api_chat
"""
import getpass
import json

import httpx

BASE_URL = "http://127.0.0.1:8000"


def stream_events(client: httpx.Client, url: str, body: dict):
    with client.stream("POST", url, json=body) as response:
        if response.status_code != 200:
            response.read()
            print(f"\n[HTTP {response.status_code}] {response.text}")
            return
        for line in response.iter_lines():
            if line.startswith("data: "):
                yield json.loads(line[len("data: "):])


def run(client: httpx.Client, url: str, body: dict) -> dict | None:
    """Print the events as they arrive. Returns the confirmation request, if there is one."""
    pending = None
    for event in stream_events(client, url, body):
        kind = event["type"]
        if kind == "node":
            print(f"  [{event['name']}]")
        elif kind == "token":
            print(event["content"], end="", flush=True)
        elif kind == "recipes":
            for number, card in enumerate(event["items"], 1):
                tag = " [AI]" if card.get("ai_generated") else ""
                print(f"\n   {number}. {card['title']}{tag} ({card['time']} min)")
        elif kind == "answer":
            print("\n\nFINAL ANSWER:\n" + event["content"])
        elif kind == "confirmation_required":
            pending = event
        elif kind == "error":
            print("\nERROR:", event["message"])
    return pending


def ask_confirmation(info: dict) -> dict:
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
            print("One item per line as  name,quantity,unit  (empty line = done):")
            items = []
            while line := input("  > ").strip():
                name, quantity, unit = (line.split(",") + ["", ""])[:3]
                items.append({"name": name, "quantity": float(quantity or 0) or None, "unit": unit or None})
            return {"approved": True, "items": items}


def main() -> None:
    email = input("email: ").strip()
    password = getpass.getpass("password: ")
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        login = client.post("/auth/login", data={"username": email, "password": password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        session_id = client.post("/chat/sessions").json()["id"]
        print(f"chat {session_id} created (type quit to leave)")
        while True:
            text = input("\nyou> ").strip()
            if text.lower() in ("quit", "exit"):
                break
            if not text:
                continue
            pending = run(client, f"/chat/sessions/{session_id}/messages", {"content": text})
            while pending:
                pending = run(client, f"/chat/sessions/{session_id}/confirm", ask_confirmation(pending))


if __name__ == "__main__":
    main()
