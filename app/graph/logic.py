"""Pure functions used by the chef graph. No LLM, no database, no LangGraph here,
so everything in this file can be unit-tested instantly."""
import re
from types import SimpleNamespace

from app.services.allergens import (
    ALLERGEN_KEYWORDS,
    canonical_allergy,
    compute_allergens,
    mentions_term,
)
from app.services.normalize import clean_list, normalize_name
from app.services.pantry_match import names_match, pantry_match
from app.services.safety import diet_claim_problems, safety_violations
from app.services.scaling import scale_quantity

INTENTS = {"find_recipe", "meal_plan", "shopping_list", "cooking_help", "save_recipe", "off_topic"}
COOKING_TASKS = {"scale", "substitute", "technique"}
VALID_MEALS = {"breakfast", "lunch", "dinner", "snack", "dessert"}
MAX_RELAX = 2  
MAX_GENERATIONS = 2 
MAX_CANDIDATES = 8  
MAX_CARDS = 3  

_DIET_RANK = {None: 0, "none": 0, "vegetarian": 1, "vegan": 2}
STAPLE_NAMES = {"salt", "pepper", "black pepper", "water", "oil", "olive oil", "vegetable oil"}

WARNING_EN = (
    "Warning: this recipe was created by AI and has not been verified in the catalog. "
    "If you have an allergy, please double-check the ingredients yourself."
)
WARNING_KA = (
    "გაფრთხილება: ეს რეცეპტი AI-მ შექმნა და კატალოგში გადამოწმებული არ არის. "
    "ალერგიის შემთხვევაში ინგრედიენტები თავად გადაამოწმეთ."
)


# ----------------------------------------------------------------- cleaning the LLM output
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
    task = str(raw.get("cooking_task") or "").strip().lower()
    ingredient = normalize_name(str(raw.get("ingredient") or ""))[:100] or None

    return {
        "ingredients": ingredients,
        "exclude_ingredients": exclude,
        "max_time_min": _int_in_range(raw.get("max_time_min"), 1, 480),
        "servings": _int_in_range(raw.get("servings"), 1, 50),
        "cuisine": cuisine,
        "meal_type": meal if meal in VALID_MEALS else None,
        "diet": diet if diet in ("vegetarian", "vegan") else None,
        "cooking_task": task if task in COOKING_TASKS else None,
        "ingredient": ingredient,
        "reference_index": _int_in_range(raw.get("reference_index"), 1, 10),
        "all_shown": raw.get("all_shown") is True,
        "min_overlap": 1 if ingredients else 0,
    }


def stricter_diet(profile_diet: str | None, request_diet: str | None) -> str | None:
    """A request can only make the diet STRICTER than the profile, never looser."""
    for diet in (profile_diet, request_diet):
        if diet not in _DIET_RANK:
            return diet  
    return max((profile_diet, request_diet), key=lambda d: _DIET_RANK[d])


# ----------------------------------------------------------------- relaxing the search
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


# ----------------------------------------------------------------- routing (edges)
def route_after_understand(state: dict) -> str:
    intent = state.get("intent")
    if intent == "error":
        return "end"
    if intent == "off_topic":
        return "refuse"
    return "context"


def route_after_context(state: dict) -> str:
    intent = state.get("intent")
    if intent == "cooking_help":
        return "helper"
    if intent == "shopping_list":
        return "shopping"
    if intent == "save_recipe":
        return "save_recipe"
    return "search"  


def route_after_prepare(state: dict) -> str:
    """After building a shopping list / preparing a recipe save: ask for confirmation,
    or go straight to the answer if there is nothing to confirm."""
    return "confirm" if state.get("pending_action") else "compose"


def route_after_confirm(state: dict) -> str:
    """Anything except an explicit True means: do not save."""
    return "save" if state.get("confirmed") is True else "compose"


def route_after_safety(state: dict) -> str:
    if state.get("safe_recipes"):
        return "compose"
    if state.get("relax_attempts", 0) < MAX_RELAX:
        return "relax"
    if state.get("generation_attempts", 0) < MAX_GENERATIONS:
        return "generate"
    return "compose"


# ----------------------------------------------------------------- ranking and cards
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
                "ai_generated": recipe.get("source") == "ai_generated",
            }
        )
    return cards


# ----------------------------------------------------------------- AI-generated recipes
def derive_diet_tags(texts: list[str]) -> list[str]:
    """Tags for an AI recipe are decided by CODE from its text, never by the LLM's word.
    A tag is granted only if no ingredient contradicts it."""
    return [
        tag
        for tag in ("vegetarian", "vegan", "gluten_free")
        if not diet_claim_problems([tag], texts)
    ]


def sanitize_draft(raw: dict, default_servings: int = 2) -> dict | None:
    """Clean a recipe invented by the LLM. Returns None if it is not usable."""
    try:
        title = str(raw.get("title") or "").strip()[:100]
        description = str(raw.get("description") or "").strip()[:300]
        servings = _int_in_range(raw.get("servings"), 1, 20) or max(1, min(default_servings, 20))
        minutes = _int_in_range(raw.get("total_time_min"), 1, 480)
        steps = [str(s).strip() for s in (raw.get("steps") or []) if str(s).strip()][:30]

        ingredients = []
        for item in raw.get("ingredients") or []:
            name = normalize_name(str(item.get("name") or ""))[:100]
            unit = normalize_name(str(item.get("unit") or ""))[:20]
            try:
                quantity = float(item.get("quantity"))
            except (TypeError, ValueError):
                continue
            if name and unit and quantity > 0:
                ingredients.append(
                    {
                        "name": name,
                        "quantity": round(quantity, 2),
                        "unit": unit,
                        "is_staple": name in STAPLE_NAMES,
                    }
                )
    except AttributeError:
        return None

    if not title or minutes is None or len(ingredients) < 2 or len(steps) < 2:
        return None
    return {
        "title": title,
        "description": description,
        "servings": servings,
        "total_time_min": minutes,
        "ingredients": ingredients,
        "steps": steps,
    }


def build_generated_candidate(draft: dict, available: list[str]) -> dict:
    """Turn a cleaned draft into the same shape as a catalog recipe. Allergens and tags are
    computed by code from the ingredient names AND the title and steps, because an LLM can
    hide an allergen in the instructions ('stir in a splash of cream')."""
    names = [i["name"] for i in draft["ingredients"]]
    scan_text = [draft["title"], *draft["steps"]]
    match = pantry_match([SimpleNamespace(**i) for i in draft["ingredients"]], available)
    return {
        "id": None,  
        "title": draft["title"],
        "description": draft["description"],
        "cuisine": None,
        "meal_type": None,
        "servings": draft["servings"],
        "total_time_min": draft["total_time_min"],
        "diet_tags": derive_diet_tags(names + scan_text),
        "allergens": compute_allergens(names + scan_text),
        "source": "ai_generated",
        "ingredients": draft["ingredients"],
        "steps": draft["steps"],
        "scan_text": scan_text,
        "match_score": match.score,
        "missing": match.missing,
        "distance": None,
    }


def ai_warning(user_text: str) -> str:
    """The mandatory AI warning, in the user's language. Added by code, not by the LLM."""
    return WARNING_KA if re.search(r"[\u10A0-\u10FF]", user_text or "") else WARNING_EN


# ----------------------------------------------------------------- medical questions

_MEDICAL_PATTERN = re.compile(
    r"\bdiabet|\bcholesterol|\bblood pressure|\bhypertensi|\bkidney(?! bean)|\bheart (?:disease|condition|problem)"
    r"|\bcancer|\bpregnan|\bbreastfeed|\bmedication|\bdisease|\billness|\bthyroid|\bgout\b|\bcrohn|\banaemi|\banemi"
    r"|დიაბეტ|ქოლესტერ|წნევ|თირკმ|ორსულ|დაავადებ|ავადმყოფ|მედიკამენტ",
    re.IGNORECASE,
)
MEDICAL_NOTICE_EN = (
    "Note: I am a cooking assistant, not a doctor. For a health condition, please ask your doctor "
    "or a dietitian what you can eat."
)
MEDICAL_NOTICE_KA = (
    "შენიშვნა: მე კულინარიული ასისტენტი ვარ და არა ექიმი. ჯანმრთელობის პრობლემის შემთხვევაში, "
    "რა შეგიძლიათ მიირთვათ, ექიმს ან დიეტოლოგს გაესაუბრეთ."
)


def needs_medical_notice(user_text: str) -> bool:
    return bool(_MEDICAL_PATTERN.search(user_text or ""))


def medical_notice(user_text: str, language: str = "English") -> str:
    georgian = (language or "").lower() == "georgian" or re.search(r"[\u10A0-\u10FF]", user_text or "")
    return MEDICAL_NOTICE_KA if georgian else MEDICAL_NOTICE_EN


def with_medical_notice(text: str, user_text: str, language: str = "English") -> str:
    if needs_medical_notice(user_text):
        return f"{text}\n\n{medical_notice(user_text, language)}"
    return text


def recipe_summary(recipe: dict) -> dict:
    """The only facts about an AI recipe the LLM gets: enough for a short introduction.
    The ingredient list and the steps are written by code (format_generated_recipe)."""
    return {
        "title": recipe["title"],
        "description": recipe.get("description", ""),
        "servings": recipe["servings"],
        "total_time_min": recipe["total_time_min"],
    }


def describe_problems(recipe: dict, allergies: list[str], diet: str | None, disliked: list[str]) -> list[str]:
    """Tell the LLM WHICH ingredient or step broke a rule, so a retry can fix exactly that."""
    problems: list[str] = []
    texts = [i["name"] for i in recipe["ingredients"]] + list(recipe.get("scan_text", []))
    for text in texts:
        shown = text if len(text) <= 60 else text[:57] + "..."
        found = set(compute_allergens([text]))
        for allergy in clean_list(allergies):
            category = canonical_allergy(allergy)
            if category in ALLERGEN_KEYWORDS:
                if category in found:
                    problems.append(f'"{shown}" contains {category}')
            elif mentions_term([text], category):
                problems.append(f'"{shown}" contains {category}')
        for term in clean_list(disliked):
            if mentions_term([text], term):
                problems.append(f'"{shown}" contains {term}, which the user dislikes')
    if diet in ("vegan", "vegetarian"):
        for problem in diet_claim_problems([diet], texts):
            problems.append(f"diet {diet}: {problem}")
    return problems[:10]


def forbidden_words(allergies: list[str], disliked: list[str]) -> list[str]:
    """Every English word the LLM must not use, spelled out, so nothing is left to guess."""
    words: list[str] = []
    for allergy in clean_list(allergies):
        category = canonical_allergy(allergy)
        words += ALLERGEN_KEYWORDS.get(category, [category])
    words += clean_list(disliked)
    return sorted({w for w in words if w.isascii()})


def sanitize_language(value) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"[A-Za-z][A-Za-z \-]{0,29}", text) else "English"


# ----------------------------------------------------------------- text written by code
LABELS = {
    "en": {"ingredients": "Ingredients", "steps": "Steps", "options": "Options",
           "minutes": "min", "servings": "servings"},
    "ka": {"ingredients": "ინგრედიენტები", "steps": "მომზადება", "options": "ვარიანტები",
           "minutes": "წთ", "servings": "პორცია"},
}


def labels_for(user_text: str, language: str = "English") -> dict:
    georgian = (language or "").lower() == "georgian" or re.search(r"[\u10A0-\u10FF]", user_text or "")
    return LABELS["ka"] if georgian else LABELS["en"]


def _fmt_qty(quantity) -> str:
    number = float(quantity)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def format_ingredient_lines(ingredients: list[dict]) -> str:
    return "\n".join(f"- {_fmt_qty(i['quantity'])} {i['unit']} {i['name']}" for i in ingredients)


def format_generated_recipe(recipe: dict, labels: dict | None = None) -> str:
    """The recipe itself, written by code from the cleaned data, so nothing can be dropped or invented."""
    labels = labels or LABELS["en"]
    lines = [f"{recipe['title']} - {recipe['total_time_min']} {labels['minutes']}, "
             f"{recipe['servings']} {labels['servings']}"]
    if recipe.get("description"):
        lines.append(recipe["description"])
    lines += ["", f"{labels['ingredients']}:", format_ingredient_lines(recipe["ingredients"]), "",
              f"{labels['steps']}:"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.get("steps", []), 1)]
    return "\n".join(lines)


def format_scaled(result: dict, labels: dict | None = None) -> str:
    labels = labels or LABELS["en"]
    return (f"{result['title']} - {result['servings']} {labels['servings']}:\n"
            + format_ingredient_lines(result["ingredients"]))


def format_options(result: dict, labels: dict | None = None) -> str:
    labels = labels or LABELS["en"]
    return f"{labels['options']}: " + ", ".join(result["options"])


# ----------------------------------------------------------------- cooking helper
def resolve_reference(last_shown: list[dict], index: int | None) -> dict | None:
    """Which previously shown recipe does the user mean? None if it is unclear."""
    if not last_shown:
        return None
    if index is not None and 1 <= index <= len(last_shown):
        return last_shown[index - 1]
    if len(last_shown) == 1:
        return last_shown[0]
    return None


def scale_recipe(recipe: dict, target_servings: int) -> dict:
    """Pure arithmetic. The LLM never multiplies anything."""
    base = recipe["servings"]
    return {
        "id": recipe.get("id"),
        "title": recipe["title"],
        "base_servings": base,
        "servings": target_servings,
        "ingredients": [
            {
                "name": i["name"],
                "quantity": scale_quantity(i["quantity"], base, target_servings),
                "unit": i["unit"],
                "is_staple": i.get("is_staple", False),
            }
            for i in recipe["ingredients"]
        ],
    }


def safe_substitutes(
    options: list[str], *, original: str | None, allergies: list[str], diet: str | None,
    disliked: list[str],
) -> tuple[list[str], int]:
    """The LLM suggests substitutes, but each one goes through the same safety check as a recipe."""
    original_name = normalize_name(original or "")
    safe: list[str] = []
    hidden = 0
    for name in clean_list([str(o) for o in options])[:8]:
        if name == original_name:
            continue
        violations = safety_violations(
            allergies=allergies,
            diet=diet,
            disliked=disliked,
            ingredient_names=[name],
            allergens=[],
            diet_tags=derive_diet_tags([name]),
        )
        if violations:
            hidden += 1
        else:
            safe.append(name)
    return safe[:5], hidden


# ----------------------------------------------------------------- shopping list and saving
def pick_recipes(last_shown: list[dict], index: int | None, all_shown: bool) -> list[dict]:
    """Which of the previously shown recipes does the user mean? Empty list = unclear."""
    if not last_shown:
        return []
    if all_shown:
        return list(last_shown)
    card = resolve_reference(last_shown, index)
    return [card] if card else []


def build_shopping_items(recipes: list[dict], pantry: list[dict]) -> list[dict]:
    """What to buy = what the recipes need - what the pantry has. Pure arithmetic, no LLM.
    - staples (salt, oil, water) are never listed
    - the same ingredient from several recipes is added up
    - a pantry item with an unknown amount counts as 'enough'
    - amounts are only subtracted when the units match (we never guess a conversion)"""
    needed: dict[tuple[str, str], dict] = {}
    for recipe in recipes:
        for ing in recipe["ingredients"]:
            if ing.get("is_staple"):
                continue
            entry = needed.setdefault(
                (ing["name"], ing["unit"]),
                {"name": ing["name"], "unit": ing["unit"], "quantity": 0.0, "recipe_ids": set()},
            )
            entry["quantity"] += ing["quantity"]
            entry["recipe_ids"].add(recipe.get("id"))

    items = []
    for entry in needed.values():
        owned = [p for p in pantry if names_match(entry["name"], p["name"])]
        if any(p.get("quantity") is None for p in owned):
            continue
        have = sum(p["quantity"] for p in owned if p.get("unit") == entry["unit"])
        missing = round(entry["quantity"] - have, 2)
        if missing <= 0:
            continue
        ids = entry["recipe_ids"]
        items.append(
            {
                "name": entry["name"],
                "quantity": missing,
                "unit": entry["unit"],
                "recipe_id": next(iter(ids)) if len(ids) == 1 else None,
            }
        )
    return items


def shopping_title(recipes: list[dict]) -> str:
    if len(recipes) == 1:
        return f"Shopping list: {recipes[0]['title']}"[:255]
    return f"Shopping list ({len(recipes)} recipes)"


def parse_confirmation(answer) -> tuple[bool, list | None]:
    """What the user answered at the confirmation step. Only an explicit True approves."""
    if isinstance(answer, bool):
        return answer, None
    if isinstance(answer, dict):
        items = answer.get("items")
        return answer.get("approved") is True, items if isinstance(items, list) else None
    return False, None


def sanitize_items(raw, original: list[dict]) -> list[dict]:
    """The user may edit the list before saving. Whatever arrives is cleaned like any other input."""
    by_name = {i["name"]: i for i in original}
    items: list[dict] = []
    seen: set[str] = set()
    for item in (raw[:100] if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        name = normalize_name(str(item.get("name") or ""))[:100]
        if not name or name in seen:
            continue
        quantity = item.get("quantity")
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            quantity = round(quantity, 2)
        unit = normalize_name(str(item.get("unit") or ""))[:20] or None
        items.append(
            {
                "name": name,
                "quantity": quantity,
                "unit": unit,
                "recipe_id": by_name.get(name, {}).get("recipe_id"),  
            }
        )
        seen.add(name)
    return items


def describe_pending(pending: dict) -> dict:
    """What the user is shown at the confirmation step (it also goes out as an SSE event)."""
    if pending["type"] == "save_shopping_list":
        return {
            "type": "confirmation_required",
            "action": "save_shopping_list",
            "title": pending["title"],
            "items": [
                {"name": i["name"], "quantity": i.get("quantity"), "unit": i.get("unit")}
                for i in pending["items"]
            ],
        }
    recipe = pending["recipe"]
    return {
        "type": "confirmation_required",
        "action": "save_recipe",
        "title": recipe["title"],
        "ai_generated": recipe.get("source") == "ai_generated",
    }


def format_items(items: list[dict]) -> str:
    lines = []
    for item in items:
        quantity = item.get("quantity")
        amount = f"{_fmt_qty(quantity)} {item.get('unit') or ''}".strip() if quantity else ""
        lines.append(f"- {amount} {item['name']}" if amount else f"- {item['name']}")
    return "\n".join(lines)


# ----------------------------------------------------------------- fallback texts
def fallback_answer(cards: list[dict], generated: dict | None = None) -> str:
    """Used when the LLM cannot write the answer: the user still gets the facts."""
    if generated:
        return format_generated_recipe(generated)
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


def fallback_action_answer(result: dict) -> str:
    status = result.get("status")
    if status == "saved" and result.get("type") == "save_shopping_list":
        return f"Saved: {result['title']} ({len(result['items'])} items)."
    if status == "saved":
        return f"Saved to your cookbook: {result['title']}."
    if status == "declined":
        return "Okay, nothing was saved."
    if status == "nothing_to_buy":
        return "You already have everything you need for this recipe."
    if status == "clarify":
        if result.get("reason") == "which_recipe":
            return "Which recipe do you mean? Please tell me its name or number."
        return "Which recipe do you mean? I don't have one to work with yet."
    return "Sorry, I couldn't save that. Nothing was changed, please try again."


def fallback_helper_answer(result: dict) -> str:
    kind = result.get("kind")
    if kind == "scale":
        return format_scaled(result)
    if kind == "substitute":
        if result.get("options"):
            return f"Instead of {result['ingredient']} you can use: " + ", ".join(result["options"]) + "."
        return f"I couldn't find a safe substitute for {result['ingredient']}."
    if kind == "clarify":
        questions = {
            "which_recipe": "Which of the recipes do you mean? Please tell me its name or number.",
            "no_recipe": "Which recipe do you mean? I don't have one to work with yet.",
            "servings": "For how many servings should I scale it?",
            "ingredient": "Which ingredient would you like to replace?",
        }
        return questions.get(result.get("reason"), "Could you tell me a bit more?")
    return "I couldn't answer that right now. Please try again in a moment."


# ----------------------------------------------------------------- helpers for messages
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
