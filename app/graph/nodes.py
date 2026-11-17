import logging
from collections import Counter

from langchain_core.messages import AIMessage

from app.graph.deps import ChefDeps
from app.graph.logic import (
    INTENTS,
    MAX_CANDIDATES,
    build_cards,
    build_query,
    fallback_answer,
    last_user_text,
    rank_candidates,
    relax,
    sanitize_constraints,
    stricter_diet,
    to_history,
)
from app.graph.state import ChefState
from app.services.normalize import clean_list
from app.services.safety import safety_violations

logger = logging.getLogger(__name__)

ERROR_TEXT = "Sorry, I couldn't process that right now. Please try again in a moment."
REFUSAL_FALLBACK = "I can only help with food, cooking and recipes. Is there something you'd like to cook?"
COMING_SOON_TEXT = "That feature is not available yet. For now I can help you find recipes."


def _turn_reset() -> dict:
    """The checkpointer remembers state between messages, so everything that belongs to ONE
    request must be cleared at the start of each turn. last_shown is deliberately kept."""
    return {
        "candidates": [],
        "safe_recipes": [],
        "blocked_summary": {},
        "relax_attempts": 0,
        "generated_recipe": None,
        "pending_action": None,
        "confirmed": None,
        "cards": [],
        "answer": "",
    }


class ChefNodes:
    def __init__(self, deps: ChefDeps):
        self.deps = deps

    async def understand_request(self, state: ChefState) -> dict:
        reset = _turn_reset()
        try:
            analysis = await self.deps.llm.analyze(to_history(state.get("messages", [])))
            intent = analysis.get("intent")
            if intent not in INTENTS:
                raise ValueError(f"unknown intent: {intent!r}")
            constraints = sanitize_constraints(analysis.get("constraints") or {})
        except Exception:
            logger.exception("understand_request failed")
            return {
                **reset,
                "intent": "error",
                "answer": ERROR_TEXT,
                "messages": [AIMessage(content=ERROR_TEXT)],
            }
        return {
            **reset,
            "intent": intent,
            "refers_to_previous": bool(analysis.get("refers_to_previous")),
            "constraints": constraints,
        }

    async def polite_refusal(self, state: ChefState) -> dict:
        payload = {"task": "refusal", "user_message": last_user_text(state.get("messages", []))}
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("polite_refusal: LLM failed, using fixed text")
            text = REFUSAL_FALLBACK
        return {"answer": text, "messages": [AIMessage(content=text)]}

    async def load_context(self, state: ChefState) -> dict:
        profile, pantry = await self.deps.load_context(state["user_id"])
        return {"profile": profile, "pantry": pantry}

    async def search_recipes(self, state: ChefState) -> dict:
        constraints = state["constraints"]
        query = build_query(last_user_text(state.get("messages", [])), constraints)
        raw = await self.deps.search(state["user_id"], constraints, query)
        mentioned = constraints.get("ingredients", [])
        available = clean_list(list(state.get("pantry", [])) + mentioned)
        ranked = rank_candidates(
            raw,
            available=available,
            mentioned=mentioned,
            min_overlap=constraints.get("min_overlap", 0),
        )
        return {"candidates": ranked[:MAX_CANDIDATES]}

    async def safety_filter(self, state: ChefState) -> dict:
        """Pure Python. The LLM is not involved and has no say."""
        profile = state["profile"]
        constraints = state["constraints"]
        allergies = clean_list(list(profile.get("allergies", [])) + constraints.get("exclude_ingredients", []))
        diet = stricter_diet(profile.get("diet"), constraints.get("diet"))
        disliked = profile.get("disliked_ingredients", [])

        safe: list[dict] = []
        blocked: Counter = Counter()
        for recipe in state.get("candidates", []):
            violations = safety_violations(
                allergies=allergies,
                diet=diet,
                disliked=disliked,
                ingredient_names=[i["name"] for i in recipe["ingredients"]],
                allergens=recipe.get("allergens", []),
                diet_tags=recipe.get("diet_tags", []),
            )
            if violations:
                blocked.update(violations)
            else:
                safe.append(recipe)
        return {"safe_recipes": safe, "blocked_summary": dict(blocked)}

    async def relax_constraints(self, state: ChefState) -> dict:
        attempts = state.get("relax_attempts", 0)
        return {
            "constraints": relax(state["constraints"], attempts),
            "relax_attempts": attempts + 1,
        }

    async def compose_answer(self, state: ChefState) -> dict:
        cards = build_cards(state.get("safe_recipes", []))
        profile = state.get("profile", {})
        payload = {
            "task": "recipes",
            "user_message": last_user_text(state.get("messages", [])),
            "recipes": cards,
            "no_results": not cards,
            "hidden_for_safety": state.get("blocked_summary", {}),
            "search_was_relaxed": state.get("relax_attempts", 0) > 0,
            "user_profile": {"allergies": profile.get("allergies", []), "diet": profile.get("diet")},
        }
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("compose_answer: LLM failed, using fallback text")
            text = fallback_answer(cards)
        return {
            "answer": text,
            "cards": cards,
            "last_shown": cards if cards else state.get("last_shown", []),
            "messages": [AIMessage(content=text)],
        }

    async def coming_soon(self, state: ChefState) -> dict:
        return {"answer": COMING_SOON_TEXT, "messages": [AIMessage(content=COMING_SOON_TEXT)]}