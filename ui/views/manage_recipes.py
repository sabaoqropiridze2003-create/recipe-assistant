import streamlit as st
from common import api, call, call_ok
from helpers import DIET_TAGS, MEAL_TYPES, clean_recipe_ingredients


def render() -> None:
    st.title("🛠 Manage recipes")
    st.caption("Admin only. Allergens are worked out by the server from the ingredients: you cannot type them.")
    client = api()

    st.subheader("Add a recipe")
    with st.form("new_recipe"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        col1, col2, col3, col4 = st.columns(4)
        cuisine = col1.text_input("Cuisine")
        meal_type = col2.selectbox("Meal", MEAL_TYPES, index=2)
        servings = col3.number_input("Servings", min_value=1, max_value=100, value=2)
        minutes = col4.number_input("Total minutes", min_value=1, max_value=1440, value=30)
        tags = st.multiselect("Diet tags", DIET_TAGS)
        steps_text = st.text_area("Steps (one per line)")
        st.markdown("**Ingredients** (tick *is_staple* for salt, oil, water...)")
        rows = st.data_editor(
            [{"name": "", "quantity": 1.0, "unit": "g", "is_staple": False}],
            num_rows="dynamic",
            key="new_recipe_ingredients",
            column_config={
                "name": st.column_config.TextColumn("Ingredient", required=True),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0),
                "unit": st.column_config.TextColumn("Unit", required=True),
                "is_staple": st.column_config.CheckboxColumn("Staple"),
            },
        )
        submitted = st.form_submit_button("Create recipe", type="primary")

    if submitted:
        body = {
            "title": title.strip(),
            "description": description.strip(),
            "cuisine": cuisine.strip() or None,
            "meal_type": meal_type,
            "servings": int(servings),
            "total_time_min": int(minutes),
            "diet_tags": tags,
            "steps": [line.strip() for line in steps_text.splitlines() if line.strip()],
            "ingredients": clean_recipe_ingredients(rows),
        }
        created = call(client.create_recipe, body)
        if created is not None:
            found = ", ".join(created["allergens"]) or "none"
            st.success(f"Created '{created['title']}'. Allergens found by the server: {found}.")

    st.subheader("Catalog")
    result = call(client.list_recipes, size=100, stop=True)
    for recipe in result["items"]:
        if recipe["source"] != "catalog":
            continue
        text_col, button_col = st.columns([6, 1])
        text_col.write(f"**{recipe['title']}** · {recipe['total_time_min']} min · contains: {', '.join(recipe['allergens']) or 'none'}")
        if button_col.button("Delete", key=f"admin_delete_{recipe['id']}"):
            if call_ok(client.delete_recipe, recipe["id"]):
                st.rerun()
