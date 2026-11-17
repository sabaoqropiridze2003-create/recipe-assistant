import logging
from collections import Counter

from langchain_core.messages import AIMessage

from app.graph.deps import ChefDeps
from app.graph.logic import (
    INTENTS,
    MAX_CANDIDATES,
    ai_warning,
    build_cards,
    build_generated_candidate,
    build_query,
    fallback_answer,
    fallback_helper_answer,
    last_user_text,
    rank_candidates,
    recipe_details,
    relax,
    resolve_reference,
    safe_substitutes,
    sanitize_constraints,
    sanitize_draft,
    scale_recipe,
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
    request must be cleared at the start of each turn. last_shown and last_generated are
    deliberately kept, so 'the second one' still works on the next message."""
    return {
        "candidates": [],
        "safe_recipes": [],
        "blocked_summary": {},
        "relax_attempts": 0,
        "generated_recipe": None,
        "generation_attempts": 0,
        "generation_feedback": [],
        "helper_result": None,
        "pending_action": None,
        "confirmed": None,
        "cards": [],
        "answer": "",
    }


class ChefNodes:
    def __init__(self, deps: ChefDeps):
        self.deps = deps

    # ------------------------------------------------------------ understanding
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
        # user_id comes from the server (JWT), never from the LLM
        profile, pantry = await self.deps.load_context(state["user_id"])
        return {"profile": profile, "pantry": pantry}

    # ------------------------------------------------------------ finding recipes
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

    def _restrictions(self, state: ChefState) -> tuple[list[str], str | None, list[str]]:
        """Allergies, diet and dislikes that apply to THIS request. Exclusions typed in the
        message are treated exactly like allergies, and they can only tighten the rules."""
        profile = state["profile"]
        constraints = state["constraints"]
        allergies = clean_list(
            list(profile.get("allergies", [])) + constraints.get("exclude_ingredients", [])
        )
        diet = stricter_diet(profile.get("diet"), constraints.get("diet"))
        return allergies, diet, profile.get("disliked_ingredients", [])

    async def safety_filter(self, state: ChefState) -> dict:
        """Pure Python. The LLM is not involved and has no say. Catalog recipes and AI recipes
        go through exactly the same check."""
        allergies, diet, disliked = self._restrictions(state)

        safe: list[dict] = []
        blocked: Counter = Counter()
        feedback: list[str] = []
        for recipe in state.get("candidates", []):
            names = [i["name"] for i in recipe["ingredients"]] + list(recipe.get("scan_text", []))
            violations = safety_violations(
                allergies=allergies,
                diet=diet,
                disliked=disliked,
                ingredient_names=names,
                allergens=recipe.get("allergens", []),
                diet_tags=recipe.get("diet_tags", []),
            )
            if violations:
                blocked.update(violations)
                if recipe.get("source") == "ai_generated":
                    feedback.extend(violations)
            else:
                safe.append(recipe)
        return {
            "safe_recipes": safe,
            "blocked_summary": dict(blocked),
            "generation_feedback": feedback,
        }

    async def relax_constraints(self, state: ChefState) -> dict:
        attempts = state.get("relax_attempts", 0)
        return {
            "constraints": relax(state["constraints"], attempts),
            "relax_attempts": attempts + 1,
        }

    async def generate_recipe(self, state: ChefState) -> dict:
        """Nothing in the catalog fits, so the LLM invents a recipe. Its output is NOT trusted:
        it is cleaned, its allergens and tags are computed by code, and then it goes through
        the same safety_filter as every other recipe."""
        attempts = state.get("generation_attempts", 0)
        profile = state["profile"]
        constraints = state["constraints"]
        allergies, diet, disliked = self._restrictions(state)

        brief = {
            "user_message": last_user_text(state.get("messages", [])),
            "ingredients_to_use": constraints.get("ingredients", []),
            "pantry": list(state.get("pantry", []))[:30],
            "must_avoid": allergies,
            "disliked": disliked,
            "diet": diet,
            "max_time_min": constraints.get("max_time_min"),
            "meal_type": constraints.get("meal_type"),
            "cuisine": constraints.get("cuisine"),
            "servings": constraints.get("servings"),
            "previous_problems": list(state.get("generation_feedback", [])),
        }
        update: dict = {"generation_attempts": attempts + 1, "candidates": []}
        try:
            raw = await self.deps.llm.generate(brief)
            draft = sanitize_draft(
                raw, default_servings=constraints.get("servings") or profile.get("default_servings", 2)
            )
        except Exception:
            logger.exception("generate_recipe failed")
            draft = None

        if draft:
            available = clean_list(list(state.get("pantry", [])) + constraints.get("ingredients", []))
            candidate = build_generated_candidate(draft, available)
            update["candidates"] = [candidate]
            update["generated_recipe"] = candidate
        return update

    # ------------------------------------------------------------ cooking help
    async def _load_recipe(self, state: ChefState, card: dict) -> dict | None:
        if card.get("id") is not None and self.deps.get_recipe:
            return await self.deps.get_recipe(state["user_id"], card["id"])
        last = state.get("last_generated")  # an AI recipe has no database id
        if last and last.get("title") == card.get("title"):
            return last
        return None

    async def cooking_helper(self, state: ChefState) -> dict:
        constraints = state["constraints"]
        task = constraints.get("cooking_task")
        text = last_user_text(state.get("messages", []))

        if task == "substitute":
            ingredient = constraints.get("ingredient")
            if not ingredient:
                return {"helper_result": {"kind": "clarify", "reason": "ingredient"}}
            try:
                options = await self.deps.llm.substitute(
                    {"ingredient": ingredient, "user_message": text}
                )
            except Exception:
                logger.exception("substitute suggestion failed")
                options = []
            allergies, diet, disliked = self._restrictions(state)
            safe, hidden = safe_substitutes(
                options, original=ingredient, allergies=allergies, diet=diet, disliked=disliked
            )
            return {
                "helper_result": {
                    "kind": "substitute",
                    "ingredient": ingredient,
                    "options": safe,
                    "hidden_count": hidden,
                }
            }

        if task == "scale":
            target = constraints.get("servings")
            if not target:
                return {"helper_result": {"kind": "clarify", "reason": "servings"}}
            last_shown = state.get("last_shown", [])
            card = resolve_reference(last_shown, constraints.get("reference_index"))
            if card is None:
                if last_shown:
                    return {
                        "helper_result": {
                            "kind": "clarify",
                            "reason": "which_recipe",
                            "options": [c["title"] for c in last_shown],
                        }
                    }
                return {"helper_result": {"kind": "clarify", "reason": "no_recipe"}}
            recipe = await self._load_recipe(state, card)
            if recipe is None:
                return {"helper_result": {"kind": "clarify", "reason": "no_recipe"}}
            return {"helper_result": {"kind": "scale", **scale_recipe(recipe, target)}}

        return {"helper_result": {"kind": "technique"}}

    # ------------------------------------------------------------ the final answer
    async def compose_answer(self, state: ChefState) -> dict:
        if state.get("intent") == "cooking_help":
            return await self._compose_helper(state)

        safe = state.get("safe_recipes", [])
        cards = build_cards(safe)
        profile = state.get("profile", {})
        user_text = last_user_text(state.get("messages", []))
        generated = next((r for r in safe if r.get("source") == "ai_generated"), None)

        payload = {
            "task": "recipes",
            "user_message": user_text,
            "recipes": cards,
            "generated_recipe": recipe_details(generated) if generated else None,
            "no_results": not cards,
            "hidden_for_safety": state.get("blocked_summary", {}),
            "search_was_relaxed": state.get("relax_attempts", 0) > 0,
            "user_profile": {"allergies": profile.get("allergies", []), "diet": profile.get("diet")},
        }
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("compose_answer: LLM failed, using fallback text")
            text = fallback_answer(cards, generated)

        if generated:  
            text = f"{text}\n\n{ai_warning(user_text)}"

        update = {
            "answer": text,
            "cards": cards,
            "last_shown": cards if cards else state.get("last_shown", []),
            "messages": [AIMessage(content=text)],
        }
        if generated:
            update["last_generated"] = generated
        return update

    async def _compose_helper(self, state: ChefState) -> dict:
        result = state.get("helper_result") or {"kind": "technique"}
        profile = state.get("profile", {})
        payload = {
            "task": "cooking_help",
            "user_message": last_user_text(state.get("messages", [])),
            "helper_result": result,
            "user_profile": {"allergies": profile.get("allergies", []), "diet": profile.get("diet")},
        }
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("compose_answer (helper): LLM failed, using fallback text")
            text = fallback_helper_answer(result)
        return {"answer": text, "messages": [AIMessage(content=text)]}

    async def coming_soon(self, state: ChefState) -> dict:
        return {"answer": COMING_SOON_TEXT, "messages": [AIMessage(content=COMING_SOON_TEXT)]}
