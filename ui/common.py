"""Small things every page needs: the API client, error handling, recipe cards and details."""
import os

import httpx
import streamlit as st
from api_client import ApiClient, ApiError
from helpers import card_caption

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")


@st.cache_resource
def http_client(base_url: str) -> httpx.Client:
    """One shared HTTP client (connection reuse). The login token is added per request."""
    return httpx.Client(base_url=base_url, timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10))


def api() -> ApiClient:
    return ApiClient(http_client(API_URL), st.session_state.get("token"))


def logout(message: str | None = None) -> None:
    st.session_state.clear()
    if message:
        st.session_state["flash"] = message
    st.rerun()


def show_error(error: ApiError) -> None:
    """A 401 means the login ran out: go back to the login page. Anything else is shown as a message."""
    if error.status == 401 and st.session_state.get("token"):
        logout("Your session has expired. Please log in again.")
    st.error(error.message)


def call(fn, *args, stop: bool = False, **kwargs):
    """Run one API call. On failure show a readable message (never a traceback) and return None."""
    try:
        return fn(*args, **kwargs)
    except ApiError as error:
        show_error(error)
        if stop:
            st.stop()
        return None


def call_ok(fn, *args, **kwargs) -> bool:
    """For actions that return nothing (delete...): True if it worked, False if an error was shown."""
    try:
        fn(*args, **kwargs)
        return True
    except ApiError as error:
        show_error(error)
        return False


def render_cards(cards: list[dict], key_prefix: str) -> None:
    """Recipe cards under an assistant message."""
    for card in cards:
        with st.container(border=True):
            st.markdown(f"**{card['title']}**")
            st.caption(card_caption(card))
            if card.get("missing"):
                st.write("You still need: " + ", ".join(card["missing"]))
            elif card.get("match") is not None:
                st.write("You have everything you need.")
            if card.get("allergens"):
                st.caption("Contains: " + ", ".join(card["allergens"]))
            if card.get("id") is not None:
                if st.button("Save to cookbook", key=f"{key_prefix}_save_{card['id']}"):
                    if call(api().save_to_cookbook, card["id"]) is not None:
                        st.success("Saved to your cookbook.")
            else:
                st.caption("To keep this recipe, tell the assistant: \"save this recipe\".")


def recipe_details(recipe_id: int, key: str) -> None:
    """Full recipe with a servings box. Scaling is done by the API (code), not here."""
    recipe = call(api().get_recipe, recipe_id)
    if recipe is None:
        return
    servings = st.number_input("Servings", min_value=1, max_value=50, value=recipe["servings"], key=f"{key}_servings")
    if servings != recipe["servings"]:
        recipe = call(api().get_recipe, recipe_id, servings) or recipe
    st.caption(f"{recipe['total_time_min']} min · {recipe['meal_type']} · {recipe.get('cuisine') or 'any cuisine'}")
    if recipe["allergens"]:
        st.caption("Contains: " + ", ".join(recipe["allergens"]))
    if recipe["description"]:
        st.write(recipe["description"])
    st.markdown("**Ingredients**")
    for item in recipe["ingredients"]:
        st.write(f"- {item['quantity']:g} {item['unit']} {item['name']}")
    st.markdown("**Steps**")
    for number, step in enumerate(recipe["steps"], 1):
        st.write(f"{number}. {step}")
