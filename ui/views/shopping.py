import streamlit as st
from common import api, call, call_ok


def render() -> None:
    st.title("🛒 Shopping lists")
    st.caption("Lists are created in the chat, after you confirm them.")
    client = api()
    lists = call(client.list_shopping_lists, stop=True)
    if not lists:
        st.info("You have no shopping lists yet. Ask the assistant: \"what do I need to buy for the first recipe?\"")
        return

    for summary in lists:
        with st.expander(f"{summary['title']}  ·  {summary['item_count']} items"):
            detail = call(client.get_shopping_list, summary["id"])
            if detail is None:
                continue
            for item in detail["items"]:
                amount = f"{item['quantity']:g} {item['unit'] or ''}".strip() if item["quantity"] is not None else ""
                label = f"{amount} {item['name']}".strip()
                bought = st.checkbox(label, value=item["is_bought"], key=f"item_{item['id']}")
                if bought != item["is_bought"]:
                    if call(client.mark_item, summary["id"], item["id"], bought) is not None:
                        st.rerun()
            if st.button("Delete this list", key=f"delete_list_{summary['id']}"):
                if call_ok(client.delete_shopping_list, summary["id"]):
                    st.rerun()
