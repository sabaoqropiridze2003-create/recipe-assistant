import streamlit as st
from common import api, call, call_ok, recipe_details
from helpers import card_caption


def render() -> None:
    st.title("📖 Cookbook")
    client = api()
    entries = call(client.list_cookbook, stop=True)
    if not entries:
        st.info("Your cookbook is empty. Save recipes from the chat or from the Recipes page.")
        return
    for entry in entries:
        recipe = entry["recipe"]
        caption = {"time": recipe["total_time_min"], "servings": recipe["servings"],
                   "ai_generated": recipe["source"] == "ai_generated"}
        with st.expander(f"{recipe['title']}  ·  {card_caption(caption)}"):
            recipe_details(recipe["id"], key=f"cookbook_{recipe['id']}")
            if st.button("Remove from cookbook", key=f"remove_{recipe['id']}"):
                if call_ok(client.remove_from_cookbook, recipe["id"]):
                    st.rerun()
