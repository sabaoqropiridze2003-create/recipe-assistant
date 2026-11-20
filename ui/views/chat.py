import streamlit as st
from api_client import ApiError
from common import api, call, call_ok, render_cards, show_error
from helpers import ALLERGY_REMINDER, clean_item_rows, node_label


def _load(session_id: int) -> None:
    """Fetch a chat from the API: its history, and whether a confirmation is waiting."""
    detail = call(api().get_session, session_id, stop=True)
    history = call(api().list_messages, session_id, stop=True)
    st.session_state["chat"] = {
        "id": session_id,
        "messages": [
            {"role": m["role"], "content": m["content"], "cards": [], "recipe_ids": m["recipe_ids"]}
            for m in history
        ],
        "pending": detail.get("pending_confirmation"),
    }


def _stream(chat: dict, events) -> None:
    """Show the answer while it arrives, then store it and redraw the page."""
    outcome = {"answer": "", "cards": [], "pending": None}
    with st.chat_message("assistant"):
        status = st.status("Thinking...", expanded=False)
        slot = st.empty()
        live = ""
        try:
            for event in events:
                kind = event["type"]
                if kind == "node":
                    status.update(label=node_label(event["name"]))
                elif kind == "token":
                    live += event["content"]
                    slot.markdown(live + "▌")
                elif kind == "recipes":
                    outcome["cards"] = event["items"]
                elif kind == "answer":
                    outcome["answer"] = event["content"]
                    slot.markdown(event["content"])  # the final text replaces the live text
                elif kind == "confirmation_required":
                    outcome["pending"] = event
                elif kind == "error":
                    outcome["answer"] = event["message"]
                    slot.error(event["message"])
        except ApiError as error:
            status.update(label="Could not send", state="error")
            pending = error.detail.get("pending_confirmation") if isinstance(error.detail, dict) else None
            if pending:  # 409: a confirmation is still open, so show it instead of an error
                chat["pending"] = pending
                st.rerun()
            show_error(error)
            return
        status.update(label="Done", state="complete")

    if outcome["answer"]:
        chat["messages"].append({"role": "assistant", "content": outcome["answer"], "cards": outcome["cards"]})
    chat["pending"] = outcome["pending"]
    st.rerun()


def _confirmation(chat: dict) -> None:
    """The assistant wants to save something. Nothing is saved until the user clicks Save."""
    pending = chat["pending"]
    with st.container(border=True):
        if pending["action"] == "save_shopping_list":
            st.markdown(f"**Save this shopping list?**  \n{pending['title']}")
            rows = st.data_editor(
                [dict(item) for item in pending["items"]],
                num_rows="dynamic",
                key=f"confirm_editor_{chat['id']}",
                column_config={
                    "name": st.column_config.TextColumn("Item", required=True),
                    "quantity": st.column_config.NumberColumn("Quantity", min_value=0),
                    "unit": st.column_config.TextColumn("Unit"),
                },
            )
            items = clean_item_rows(rows)
        else:
            kind = "an AI-created recipe" if pending.get("ai_generated") else "a recipe"
            st.markdown(f"**Save {kind} to your cookbook?**  \n{pending['title']}")
            items = None
        save_col, cancel_col = st.columns(2)
        approved = None
        if save_col.button("Save", type="primary", width="stretch"):
            approved = True
        if cancel_col.button("Cancel", width="stretch"):
            approved = False
    if approved is not None:
        chat["pending"] = None
        _stream(chat, api().stream_confirm(chat["id"], approved, items if approved else None))


def render() -> None:
    client = api()
    st.title("💬 Chat")

    # --- the list of chats (sidebar) ---
    sessions = call(client.list_sessions, stop=True)
    if not sessions:
        created = call(client.create_session, stop=True)
        sessions = [created]
    ids = [s["id"] for s in sessions]
    titles = {s["id"]: s["title"] for s in sessions}

    with st.sidebar:
        if st.button("➕ New chat", width="stretch"):
            created = call(client.create_session)
            if created:
                st.session_state["current_session"] = created["id"]
                st.rerun()
        current = st.session_state.get("current_session")
        if current not in ids:
            current = ids[0]
        current = st.radio(
            "Your chats", ids, index=ids.index(current), format_func=lambda i: titles[i],
            label_visibility="collapsed",
        )
        st.session_state["current_session"] = current
        if st.button("🗑 Delete this chat", width="stretch"):
            if call_ok(client.delete_session, current):
                st.session_state.pop("current_session", None)
                st.session_state.pop("chat", None)
                st.rerun()

    if st.session_state.get("chat", {}).get("id") != current:
        _load(current)
    chat = st.session_state["chat"]

    # --- a reminder when no allergies are set ---
    profile = call(client.get_profile)
    if profile is not None and not profile["allergies"]:
        st.info(ALLERGY_REMINDER)
        st.caption("Open **Profile** in the menu on the left to set them.")

    # --- the conversation ---
    if not chat["messages"]:
        st.caption("Tell me what you would like to cook, or what you have in the fridge.")
    for index, message in enumerate(chat["messages"]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("cards"):
                render_cards(message["cards"], key_prefix=f"m{index}")

    if chat["pending"]:
        _confirmation(chat)
        st.chat_input("Answer the question above first", disabled=True)
        return

    prompt = st.chat_input("Ask for a recipe, or tell me what you have...", max_chars=1000)
    if prompt:
        chat["messages"].append({"role": "user", "content": prompt, "cards": []})
        with st.chat_message("user"):
            st.markdown(prompt)
        _stream(chat, client.stream_message(chat["id"], prompt))
