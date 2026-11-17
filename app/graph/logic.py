from types import SimpleNamespace

from app.services.allergens import compute_allergens
from app.services.normalize import clean_list
from app.services.pantry_match import names_match, pantry_match

INTENTS = {"find_recipe", "meal_plan", "shopping_list", "cooking_help", "off_topic"}
VALID_MEALS = {"breakfast", "lunch", "dinner", "snack", "dessert"}
MAX_RELAX = 2  
MAX_CANDIDATES = 8  
MAX_CARDS = 3  

_DIET_RANK = {None: 0, "none": 0, "vegetarian": 1, "vegan": 2}



def _int_in_range(value, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def sanitize_constraints(raw: dict) -> dict:
    """Never trust the LLM: clamp numbers, normalize text, drop anything unexpected."""
    ingredients = clean_list([str(x) for x in (raw.get("ingredients") or [])])[:20]
    exclude = clean_list([str(x) for x in (raw.get("exclude_ingredients") or [])])[:20]

    meal = str(raw.get("meal_type") or "").strip().lower()
    cuisine = str(raw.get("cuisine") or "").strip().lower() or None
    diet = str(raw.get("diet") or "").strip().lower()

    return {
        "ingredients": ingredients,
        "exclude_ingredients": exclude,
        "max_time_min": _int_in_range(raw.get("max_time_min"), 1, 480),
        "servings": _int_in_range(raw.get("servings"), 1, 50),
        "cuisine": cuisine,
        "meal_type": meal if meal in VALID_MEALS else None,
        "diet": diet if diet in ("vegetarian", "vegan") else None,
        "min_overlap": 1 if ingredients else 0,
    }


def stricter_diet(profile_diet: str | None, request_diet: str | None) -> str | None:
    """A request can only make the diet STRICTER than the profile, never looser."""
    for diet in (profile_diet, request_diet):
        if diet not in _DIET_RANK:
            return diet  
    return max((profile_diet, request_diet), key=lambda d: _DIET_RANK[d])



def relax(constraints: dict, attempt: int) -> dict:
    """Loosen the SEARCH conditions. attempt = relaxations already made (0 = the first one).
    Allergies and diet are not even passed in here, and exclusions are kept."""
    relaxed = dict(constraints)
    if attempt == 0:
        had_cuisine = bool(relaxed.get("cuisine"))
        had_time = bool(relaxed.get("max_time_min"))
        relaxed["cuisine"] = None
        if had_time:
            relaxed["max_time_min"] = int(round(relaxed["max_time_min"] * 1.5))
        if not had_cuisine and not had_time:
            relaxed["min_overlap"] = 0  
    else:
        relaxed["min_overlap"] = 0
    return relaxed


def route_after_understand(state: dict) -> str:
    intent = state.get("intent")
    if intent == "error":
        return "end"
    if intent == "off_topic":
        return "refuse"
    return "context"


def route_after_context(state: dict) -> str:
    return "search" if state.get("intent") in ("find_recipe", "meal_plan") else "not_ready"


def route_after_safety(state: dict) -> str:
    if state.get("safe_recipes"):
        return "compose"
    if state.get("relax_attempts", 0) < MAX_RELAX:
        return "relax"
    return "generate"



def rank_candidates(raw: list[dict], *, available: list[str], mentioned: list[str], min_overlap: int):
    """Add the pantry match score to each recipe, drop recipes that use none of the
    ingredients the user mentioned (if required), and sort best first."""
    ranked = []
    for recipe in raw:
        ingredients = [SimpleNamespace(**i) for i in recipe["ingredients"]]
        match = pantry_match(ingredients, available)
        overlap = sum(
            1
            for ing in ingredients
            if not ing.is_staple and any(names_match(ing.name, m) for m in mentioned)
        )
        if overlap < min_overlap:
            continue
        ranked.append(
            {**recipe, "match_score": match.score, "missing": match.missing, "overlap": overlap}
        )

    def sort_key(recipe: dict):
        distance = recipe.get("distance")
        return (-recipe["match_score"], 9.9 if distance is None else distance)

    ranked.sort(key=sort_key)
    return ranked


def build_cards(recipes: list[dict], limit: int = MAX_CARDS) -> list[dict]:
    cards = []
    for recipe in recipes[:limit]:
        names = [i["name"] for i in recipe["ingredients"]]
        cards.append(
            {
                "id": recipe["id"],
                "title": recipe["title"],
                "description": recipe.get("description", ""),
                "time": recipe["total_time_min"],
                "servings": recipe["servings"],
                "missing": recipe.get("missing", []),
                "match": recipe.get("match_score", 0.0),
                "allergens": sorted(set(recipe.get("allergens", [])) | set(compute_allergens(names))),
                "source": recipe.get("source", "catalog"),
            }
        )
    return cards


def fallback_answer(cards: list[dict]) -> str:
    """Used when the LLM cannot write the answer: the user still gets the facts."""
    if not cards:
        return (
            "I couldn't find a suitable recipe for this request. "
            "Try changing the time, the ingredients or the cuisine."
        )
    lines = ["Here is what I found:"]
    for card in cards:
        missing = ", ".join(card["missing"]) if card["missing"] else "nothing"
        lines.append(f"- {card['title']} ({card['time']} min). Missing: {missing}.")
    return "\n".join(lines)



def last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(message.content)
    return ""


def to_history(messages: list, limit: int = 10, max_chars: int = 1000) -> list[tuple[str, str]]:
    """Only the last few messages, each cut to a maximum length (cost control)."""
    history = []
    for message in messages[-limit:]:
        role = "user" if getattr(message, "type", None) == "human" else "assistant"
        history.append((role, str(message.content)[:max_chars]))
    return history


def build_query(user_text: str, constraints: dict) -> str:
    query = user_text
    if constraints.get("ingredients"):
        query += ". Ingredients: " + ", ".join(constraints["ingredients"])
    return query