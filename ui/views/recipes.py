import streamlit as st
from common import api, call, recipe_details
from helpers import DIET_TAGS, MEAL_TYPES, card_caption

PAGE_SIZE = 10


def render() -> None:
    st.title("🍽 Recipes")
    client = api()

    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        search = col1.text_input("Search")
        meal_type = col2.selectbox("Meal", [""] + MEAL_TYPES, format_func=lambda v: v or "any")
        diet = col3.selectbox("Diet", [""] + DIET_TAGS, format_func=lambda v: v or "any")
        col4, col5 = st.columns(2)
        cuisine = col4.text_input("Cuisine")
        max_time = col5.number_input("Max time (minutes, 0 = any)", min_value=0, value=0, step=5)

    page = st.number_input("Page", min_value=1, value=1, step=1)
    result = call(
        client.list_recipes, search=search, meal_type=meal_type, diet=diet, cuisine=cuisine,
        max_time=max_time or None, page=int(page), size=PAGE_SIZE, stop=True,
    )
    st.caption(f"{result['total']} recipes found")
    if not result["items"]:
        st.info("No recipes match these filters.")
        return
    for recipe in result["items"]:
        caption = {"time": recipe["total_time_min"], "servings": recipe["servings"],
                   "ai_generated": recipe["source"] == "ai_generated"}
        with st.expander(f"{recipe['title']}  ·  {card_caption(caption)}"):
            recipe_details(recipe["id"], key=f"catalog_{recipe['id']}")
            if st.button("Save to cookbook", key=f"catalog_save_{recipe['id']}"):
                if call(client.save_to_cookbook, recipe["id"]) is not None:
                    st.success("Saved to your cookbook.")
