import streamlit as st
from common import api, call, call_ok


def render() -> None:
    st.title("🥕 Pantry")
    st.caption("What you have at home. The assistant uses it to suggest recipes and to build shopping lists.")
    client = api()

    with st.form("add_pantry_item", clear_on_submit=True):
        name_col, qty_col, unit_col = st.columns([3, 1, 1])
        name = name_col.text_input("Item")
        quantity = qty_col.number_input("Quantity", min_value=0.0, value=0.0, step=1.0)
        unit = unit_col.text_input("Unit", placeholder="g, ml, pcs")
        submitted = st.form_submit_button("Add")
    st.caption("Leave the quantity at 0 if you do not know how much you have.")
    if submitted:
        if not name.strip():
            st.warning("Please type the name of the item.")
        elif call(client.add_pantry, name.strip(), quantity or None, unit.strip() or None) is not None:
            st.rerun()

    items = call(client.list_pantry, stop=True)
    if not items:
        st.info("Your pantry is empty.")
        return
    for item in items:
        text_col, delete_col = st.columns([6, 1])
        amount = f"{item['quantity']:g} {item['unit'] or ''}".strip() if item["quantity"] is not None else "amount unknown"
        text_col.write(f"**{item['name']}** · {amount}")
        if delete_col.button("Remove", key=f"del_pantry_{item['id']}"):
            if call_ok(client.delete_pantry, item["id"]):
                st.rerun()
