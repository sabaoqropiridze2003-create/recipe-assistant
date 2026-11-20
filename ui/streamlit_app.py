"""The Streamlit app. Start it from the project root with:   streamlit run ui/app.py

It never touches the database or the AI graph: everything goes through the FastAPI service
(see api_client.py), and the login token lives in st.session_state."""
import streamlit as st
from api_client import ApiClient, ApiError
from common import API_URL, api, http_client, logout
from helpers import visible_pages
from views import analytics, chat, cookbook, manage_recipes, pantry, profile, recipes, shopping

st.set_page_config(page_title="Recipe Assistant", page_icon="🍳", layout="wide")

# key -> (function that draws the page, title, icon)
PAGES = {
    "chat": (chat.render, "Chat", "💬"),
    "recipes": (recipes.render, "Recipes", "🍽"),
    "cookbook": (cookbook.render, "Cookbook", "📖"),
    "pantry": (pantry.render, "Pantry", "🥕"),
    "shopping": (shopping.render, "Shopping lists", "🛒"),
    "profile": (profile.render, "Profile", "👤"),
    "manage_recipes": (manage_recipes.render, "Manage recipes", "🛠"),
    "analytics": (analytics.render, "Analytics", "📊"),
}


def show_login() -> None:
    st.title("🍳 Recipe Assistant")
    flash = st.session_state.pop("flash", None)
    if flash:
        st.warning(flash)
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary")
        if submitted:
            try:
                token = ApiClient(http_client(API_URL)).login(email.strip(), password)
                user = ApiClient(http_client(API_URL), token).me()
            except ApiError as error:
                st.error(error.message)
                return
            st.session_state["token"] = token
            st.session_state["user"] = user
            st.rerun()

    with register_tab:
        with st.form("register_form"):
            new_email = st.text_input("Email", key="reg_email")
            full_name = st.text_input("Full name")
            new_password = st.text_input("Password (at least 8 characters)", type="password", key="reg_password")
            registered = st.form_submit_button("Create account")
        if registered:
            try:
                ApiClient(http_client(API_URL)).register(new_email.strip(), full_name.strip(), new_password)
            except ApiError as error:
                st.error(error.message)
                return
            st.success("Account created. You can log in now.")


def main() -> None:
    if not st.session_state.get("token"):
        show_login()
        return

    user = st.session_state["user"]
    pages = []
    for key in visible_pages(user["role"]):  # admin pages exist only for admins
        function, title, icon = PAGES[key]
        if key == "chat":  # the start page: its URL is the root of the site
            pages.append(st.Page(function, title=title, icon=icon, default=True))
        else:
            pages.append(st.Page(function, title=title, icon=icon, url_path=key))

    with st.sidebar:
        st.caption(f"Logged in as **{user['full_name']}**" + (" (admin)" if user["role"] == "admin" else ""))
        if st.button("Log out", width="stretch"):
            logout()
    st.navigation(pages).run()


main()
