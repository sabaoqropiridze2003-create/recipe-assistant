import streamlit as st
from common import api, call
from helpers import COMMON_ALLERGIES, DIETS, split_csv


def render() -> None:
    st.title("👤 Profile")
    st.caption("The assistant never shows a recipe that breaks these rules.")
    client = api()
    profile = call(client.get_profile, stop=True)

    known = [a for a in profile["allergies"] if a in COMMON_ALLERGIES]
    other = [a for a in profile["allergies"] if a not in COMMON_ALLERGIES]
    diet = profile["diet"] if profile["diet"] in DIETS else "none"

    with st.form("profile_form"):
        allergies = st.multiselect("Allergies", COMMON_ALLERGIES, default=known)
        other_text = st.text_input("Other allergies (separate with commas)", value=", ".join(other))
        chosen_diet = st.selectbox("Diet", DIETS, index=DIETS.index(diet))
        disliked = st.text_input(
            "Ingredients you dislike (separate with commas)", value=", ".join(profile["disliked_ingredients"])
        )
        servings = st.number_input("Default servings", min_value=1, max_value=20, value=profile["default_servings"])
        submitted = st.form_submit_button("Save", type="primary")

    if submitted:
        body = {
            "allergies": allergies + split_csv(other_text),
            "diet": chosen_diet,
            "disliked_ingredients": split_csv(disliked),
            "default_servings": int(servings),
        }
        if call(client.save_profile, body) is not None:
            st.success("Profile saved.")
