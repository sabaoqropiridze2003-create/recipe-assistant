from pathlib import Path

from helpers import (
    ADMIN_PAGES,
    USER_PAGES,
    card_caption,
    clean_item_rows,
    clean_recipe_ingredients,
    friendly_error,
    node_label,
    parse_sse_line,
    split_csv,
    visible_pages,
)

NAN = float("nan")


# ---- roles ----

def test_normal_users_never_see_admin_pages():
    for role in ("user", None, "", "superuser", "ADMIN"):
        pages = visible_pages(role)
        assert pages == USER_PAGES
        assert not set(ADMIN_PAGES) & set(pages)


def test_admins_see_everything():
    assert visible_pages("admin") == USER_PAGES + ADMIN_PAGES


def test_the_ui_never_touches_the_database_or_the_graph():
    ui_folder = Path(__file__).parent.parent / "ui"
    forbidden = ("import app", "from app", "sqlalchemy", "langgraph", "langchain", "psycopg", "asyncpg")
    for path in ui_folder.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for word in forbidden:
            assert word not in source, f"{path.name} must only talk to the API, but it contains '{word}'"


# ---- errors are readable ----

def test_every_error_status_has_a_readable_message():
    assert "session has expired" in friendly_error(401, "Invalid or expired token")
    assert friendly_error(401, "Incorrect email or password") == "Incorrect email or password"
    assert "permission" in friendly_error(403, "Admin only")
    assert friendly_error(404, "Chat not found") == "Chat not found"
    assert "Cannot reach" in friendly_error(0, None)
    assert "too long" in friendly_error(-1, None)
    assert friendly_error(429, "Too many messages. Please try again in 60 seconds.").startswith("Too many")
    assert "unavailable" in friendly_error(503, None)
    assert "error 500" in friendly_error(500, "Traceback (most recent call last): secret details")


def test_internal_details_of_a_server_error_never_reach_the_user():
    assert "secret" not in friendly_error(500, "Traceback ... secret ...")


def test_conflict_with_a_pending_confirmation_shows_its_message():
    detail = {"message": "Please answer the pending confirmation first.", "pending_confirmation": {"x": 1}}
    assert friendly_error(409, detail) == "Please answer the pending confirmation first."


def test_validation_errors_name_the_field():
    detail = [{"loc": ["body", "password"], "msg": "String should have at least 8 characters"}]
    assert friendly_error(422, detail) == "Please check your input. password: String should have at least 8 characters"


# ---- the stream ----

def test_sse_lines():
    assert parse_sse_line('data: {"type": "token", "content": "Hi"}') == {"type": "token", "content": "Hi"}
    assert parse_sse_line("") is None
    assert parse_sse_line(": keep-alive") is None
    assert parse_sse_line("data: not json") is None
    assert parse_sse_line('data: {"no": "type"}') is None
    assert parse_sse_line('data: {"type": "token", "content": "გამარჯობა"}')["content"] == "გამარჯობა"


# ---- editable tables ----

def test_table_rows_become_api_items():
    rows = [
        {"name": " Carrot ", "quantity": 150.0, "unit": "g"},
        {"name": "bread", "quantity": NAN, "unit": None},  
        {"name": "", "quantity": 1, "unit": "g"},  
        {"name": None, "quantity": None, "unit": None},  
        {"name": NAN, "quantity": 1, "unit": "g"},
    ]
    assert clean_item_rows(rows) == [
        {"name": "Carrot", "quantity": 150.0, "unit": "g"},
        {"name": "bread", "quantity": None, "unit": None},
    ]
    assert clean_item_rows(None) == []


# ---- small formatting helpers ----

def test_small_helpers():
    assert split_csv(" dairy, nuts ,, ") == ["dairy", "nuts"]
    assert split_csv("") == []
    assert card_caption({"time": 20, "servings": 2}) == "20 min · 2 servings"
    assert card_caption({"time": 10, "servings": 2, "ai_generated": True}).endswith("created by AI")
    assert node_label("search_recipes") == "Searching recipes..."
    assert node_label("something_new") == "Working..."


def test_a_list_of_plain_sentences_is_shown_as_one_message():
    detail = ["tagged vegan but contains dairy or eggs", "tagged gluten_free but contains gluten"]
    assert friendly_error(422, detail) == (
        "Please check your input. tagged vegan but contains dairy or eggs; tagged gluten_free but contains gluten"
    )


def test_recipe_ingredient_rows():
    rows = [
        {"name": " Butter ", "quantity": 50, "unit": "g", "is_staple": False},
        {"name": "salt", "quantity": 1.0, "unit": "tsp", "is_staple": True},
        {"name": "", "quantity": 1, "unit": "g", "is_staple": False},  
        {"name": "flour", "quantity": NAN, "unit": "g"},  
        {"name": "milk", "quantity": 0, "unit": "ml"},  
        {"name": "water", "quantity": 100, "unit": None},  
        {"name": "egg", "quantity": "two", "unit": "pcs"},  
    ]
    assert clean_recipe_ingredients(rows) == [
        {"name": "Butter", "quantity": 50.0, "unit": "g", "is_staple": False},
        {"name": "salt", "quantity": 1.0, "unit": "tsp", "is_staple": True},
    ]
