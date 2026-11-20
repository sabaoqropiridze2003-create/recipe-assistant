"""Pure helper functions for the UI. No Streamlit and no HTTP in this file, so it is easy to test."""
import json
import math

USER_PAGES = ["chat", "recipes", "cookbook", "pantry", "shopping", "profile"]
ADMIN_PAGES = ["manage_recipes", "analytics"]

COMMON_ALLERGIES = ["dairy", "nuts", "gluten", "eggs", "seafood"]
DIETS = ["none", "vegetarian", "vegan"]
MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "dessert"]
DIET_TAGS = ["vegetarian", "vegan", "gluten_free"]

NODE_LABELS = {
    "understand_request": "Understanding your request...",
    "load_context": "Reading your profile and pantry...",
    "search_recipes": "Searching recipes...",
    "safety_filter": "Checking allergies and diet...",
    "relax_constraints": "Widening the search...",
    "generate_recipe": "Creating a new recipe...",
    "cooking_helper": "Working on your cooking question...",
    "build_shopping_list": "Building your shopping list...",
    "prepare_save_recipe": "Preparing to save the recipe...",
    "confirm_action": "Waiting for your confirmation...",
    "save_pending_action": "Saving...",
    "compose_answer": "Writing the answer...",
    "polite_refusal": "Writing the answer...",
}

ALLERGY_REMINDER = (
    "Set your allergies so the assistant can suggest safe recipes.\n\n"
    "დააყენეთ ალერგიები, რომ ასისტენტმა უსაფრთხო რეცეპტები შემოგთავაზოთ"
)


def visible_pages(role: str | None) -> list[str]:
    """Which pages a user sees. Admin pages only for the admin role. This only hides menu entries:
    the backend refuses admin endpoints to everyone else anyway (403)."""
    pages = list(USER_PAGES)
    if role == "admin":
        pages += ADMIN_PAGES
    return pages


def node_label(name: str) -> str:
    return NODE_LABELS.get(name, "Working...")


def split_csv(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def card_caption(card: dict) -> str:
    parts = [f"{card['time']} min", f"{card['servings']} servings"]
    if card.get("ai_generated"):
        parts.append("created by AI")
    return " · ".join(parts)


def parse_sse_line(line: str) -> dict | None:
    """One line of a Server-Sent Events stream -> an event, or None for blank and other lines."""
    if not line.startswith("data: "):
        return None
    try:
        event = json.loads(line[len("data: "):])
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) and "type" in event else None


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or value == ""


def clean_item_rows(rows) -> list[dict]:
    """Rows from an editable table -> items for the API. Empty rows are dropped, and empty
    cells (None, NaN, '') become None."""
    items = []
    for row in rows or []:
        name = row.get("name")
        if _is_blank(name) or not str(name).strip():
            continue
        quantity = row.get("quantity")
        unit = row.get("unit")
        items.append(
            {
                "name": str(name).strip(),
                "quantity": None if _is_blank(quantity) else float(quantity),
                "unit": None if _is_blank(unit) else str(unit).strip(),
            }
        )
    return items


def clean_recipe_ingredients(rows) -> list[dict]:
    """Rows of the admin's ingredient table -> ingredients for POST /recipes. Incomplete rows are dropped."""
    ingredients = []
    for row in rows or []:
        name, unit, quantity = row.get("name"), row.get("unit"), row.get("quantity")
        if _is_blank(name) or _is_blank(unit) or _is_blank(quantity):
            continue
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            continue
        if not str(name).strip() or not str(unit).strip() or quantity <= 0:
            continue
        ingredients.append(
            {
                "name": str(name).strip(),
                "quantity": quantity,
                "unit": str(unit).strip(),
                "is_staple": row.get("is_staple") is True,
            }
        )
    return ingredients


def error_text(detail) -> str | None:
    """FastAPI sends the error as text, as a list (validation) or as a dict (our 409)."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        return detail.get("message") or detail.get("detail")
    if isinstance(detail, list):
        problems = []
        for item in detail:
            if isinstance(item, str):  # e.g. our diet-tag check sends a list of sentences
                problems.append(item)
            elif isinstance(item, dict):
                field = ".".join(str(p) for p in item.get("loc", []) if p not in ("body", "query"))
                problems.append(f"{field}: {item.get('msg', 'invalid')}" if field else item.get("msg", "invalid"))
        return "; ".join(problems) or None
    return None


def friendly_error(status: int, detail) -> str:
    """A message a normal person can understand. Never a traceback, never internal details.
    status 0 = the server could not be reached, -1 = it took too long."""
    text = error_text(detail)
    if status == 0:
        return "Cannot reach the server. Is the API running?"
    if status == -1:
        return "The server took too long to answer (the AI may be busy). Please try again."
    if status == 401:
        if text in (None, "Invalid or expired token"):
            return "Your session has expired. Please log in again."
        return text
    if status == 403:
        return "You do not have permission to do this."
    if status == 404:
        return text or "That was not found."
    if status == 409:
        return text or "This conflicts with the current state. Please refresh and try again."
    if status == 422:
        return f"Please check your input. {text}" if text else "Please check your input."
    if status == 429:
        return text or "Too many requests. Please wait a bit and try again."
    if status in (502, 503):
        return text or "The service is temporarily unavailable. Please try again later."
    return f"Something went wrong (error {status}). Please try again."
