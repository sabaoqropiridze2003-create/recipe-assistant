import logging
from collections import Counter

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.graph.deps import ChefDeps
from app.graph.logic import (
    INTENTS,
    MAX_CANDIDATES,
    ai_warning,
    build_cards,
    build_shopping_items,
    build_generated_candidate,
    build_query,
    describe_pending,
    describe_problems,
    fallback_action_answer,
    fallback_answer,
    fallback_helper_answer,
    forbidden_words,
    format_generated_recipe,
    format_items,
    format_options,
    format_scaled,
    labels_for,
    last_user_text,
    parse_confirmation,
    pick_recipes,
    rank_candidates,
    recipe_summary,
    relax,
    resolve_reference,
    safe_substitutes,
    sanitize_constraints,
    sanitize_items,
    sanitize_draft,
    sanitize_language,
    scale_recipe,
    shopping_title,
    stricter_diet,
    to_history,
    with_medical_notice,
)
from app.graph.state import ChefState
from app.services.normalize import clean_list
from app.services.safety import safety_violations

logger = logging.getLogger(__name__)

ERROR_TEXT = "Sorry, I couldn't process that right now. Please try again in a moment."
REFUSAL_FALLBACK = "I can only help with food, cooking and recipes. Is there something you'd like to cook?"
NEW_RECIPE_INTRO = "I created a new recipe for you:"


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
        "action_result": None,
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
            "language": sanitize_language(analysis.get("language")),
            "refers_to_previous": bool(analysis.get("refers_to_previous")),
            "constraints": constraints,
        }

    async def polite_refusal(self, state: ChefState) -> dict:
        payload = {
            "task": "refusal",
            "user_message": last_user_text(state.get("messages", [])),
            "reply_language": state.get("language", "English"),
        }
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("polite_refusal: LLM failed, using fixed text")
            text = REFUSAL_FALLBACK
        text = with_medical_notice(text, payload["user_message"], payload["reply_language"])
        return {"answer": text, "messages": [AIMessage(content=text)]}

    async def load_context(self, state: ChefState) -> dict:
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
            if not violations:
                safe.append(recipe)
            elif recipe.get("source") == "ai_generated":
                feedback.extend(describe_problems(recipe, allergies, diet, disliked) or violations)
            else:
                blocked.update(violations)

        update: dict = {"safe_recipes": safe, "generation_feedback": feedback}
        if state.get("generation_attempts", 0) == 0:
            update["blocked_summary"] = dict(blocked)
        return update

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
            "language": state.get("language", "English"),
            "ingredients_to_use": constraints.get("ingredients", []),
            "pantry": list(state.get("pantry", []))[:30],
            "must_avoid": allergies,
            "forbidden_words": forbidden_words(allergies, disliked),
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
            candidate["meal_type"] = constraints.get("meal_type")
            update["candidates"] = [candidate]
            update["generated_recipe"] = candidate
        return update

    # ------------------------------------------------------------ cooking help
    async def _load_recipe(self, state: ChefState, card: dict) -> dict | None:
        if card.get("id") is not None and self.deps.get_recipe:
            return await self.deps.get_recipe(state["user_id"], card["id"])
        last = state.get("last_generated")  
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
        if state.get("intent") in ("shopping_list", "save_recipe"):
            return await self._compose_action(state)

        safe = state.get("safe_recipes", [])
        cards = build_cards(safe)
        profile = state.get("profile", {})
        user_text = last_user_text(state.get("messages", []))
        language = state.get("language", "English")
        generated = next((r for r in safe if r.get("source") == "ai_generated"), None)

        payload = {
            "task": "recipes",
            "user_message": user_text,
            "reply_language": language,
            "recipes": cards,
            "generated_recipe": recipe_summary(generated) if generated else None,
            "ai_generation_failed": state.get("generation_attempts", 0) > 0 and generated is None,
            "no_results": not cards,
            "hidden_for_safety": state.get("blocked_summary", {}),
            "search_was_relaxed": state.get("relax_attempts", 0) > 0,
            "user_profile": {"allergies": profile.get("allergies", []), "diet": profile.get("diet")},
        }
        try:
            text = await self.deps.llm.compose(payload)
        except Exception:
            logger.exception("compose_answer: LLM failed, using fallback text")
            text = NEW_RECIPE_INTRO if generated else fallback_answer(cards)

        text = with_medical_notice(text, user_text, language)
        if generated:
            body = format_generated_recipe(generated, labels_for(user_text, language))
            text = f"{text}\n\n{body}\n\n{ai_warning(user_text)}"

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
        user_text = last_user_text(state.get("messages", []))
        language = state.get("language", "English")
        payload = {
            "task": "cooking_help",
            "user_message": user_text,
            "reply_language": language,
            "helper_result": result,
            "user_profile": {"allergies": profile.get("allergies", []), "diet": profile.get("diet")},
        }
        try:
            text = await self.deps.llm.compose(payload)
            labels = labels_for(user_text, language)
            if result.get("kind") == "scale":
                text = f"{text}\n\n{format_scaled(result, labels)}"
            elif result.get("kind") == "substitute" and result.get("options"):
                text = f"{text}\n\n{format_options(result, labels)}"
        except Exception:
            logger.exception("compose_answer (helper): LLM failed, using fallback text")
            text = fallback_helper_answer(result)
        text = with_medical_notice(text, user_text, language)
        return {"answer": text, "messages": [AIMessage(content=text)]}

    # ------------------------------------------------------------ actions that write to the database
    async def build_shopping_list(self, state: ChefState) -> dict:
        """What to buy = recipe ingredients - pantry. All arithmetic is code. Nothing is saved here."""
        constraints = state["constraints"]
        last_shown = state.get("last_shown", [])
        cards = pick_recipes(last_shown, constraints.get("reference_index"), constraints.get("all_shown"))
        if not cards:
            return {"action_result": self._clarify(last_shown)}

        recipes = []
        for card in cards:
            recipe = await self._load_recipe(state, card)
            if recipe:
                target = constraints.get("servings")
                recipes.append(scale_recipe(recipe, target) if target else recipe)
        if not recipes:
            return {"action_result": self._clarify([])}

        pantry = await self.deps.get_pantry(state["user_id"]) if self.deps.get_pantry else []
        items = build_shopping_items(recipes, pantry)
        if not items:
            return {"action_result": {"status": "nothing_to_buy", "type": "save_shopping_list"}}
        return {
            "pending_action": {
                "type": "save_shopping_list",
                "title": shopping_title(recipes),
                "items": items,
            }
        }

    async def prepare_save_recipe(self, state: ChefState) -> dict:
        """Which recipe does the user want in the cookbook? Nothing is saved here."""
        constraints = state["constraints"]
        last_shown = state.get("last_shown", [])
        cards = pick_recipes(last_shown, constraints.get("reference_index"), False)
        if not cards:
            return {"action_result": self._clarify(last_shown)}
        recipe = await self._load_recipe(state, cards[0])
        if recipe is None:
            return {"action_result": self._clarify([])}
        return {"pending_action": {"type": "save_recipe", "recipe": recipe}}

    def _clarify(self, last_shown: list[dict]) -> dict:
        if last_shown:
            return {
                "status": "clarify",
                "reason": "which_recipe",
                "options": [c["title"] for c in last_shown],
            }
        return {"status": "clarify", "reason": "no_recipe"}

    async def confirm_action(self, state: ChefState) -> dict:
        """The graph STOPS here and waits. When the user answers, this node runs again from the
        top and interrupt() returns their answer, so nothing with side effects may come before it."""
        pending = state["pending_action"]
        answer = interrupt(describe_pending(pending))

        approved, edited = parse_confirmation(answer)
        update: dict = {"confirmed": approved}
        if approved and pending["type"] == "save_shopping_list" and edited is not None:
            items = sanitize_items(edited, pending["items"])
            if items:
                update["pending_action"] = {**pending, "items": items}
            else:  
                update["confirmed"] = False
        if update["confirmed"] is not True:
            update["action_result"] = {"status": "declined", "type": pending["type"]}
        return update

    async def save_pending_action(self, state: ChefState) -> dict:
        """The only place where the assistant writes to the database, and only after a 'yes'.
        user_id comes from the server and the data comes from the state, never from the client."""
        pending = state["pending_action"]
        user_id = state["user_id"]
        try:
            if pending["type"] == "save_shopping_list":
                list_id = await self.deps.save_shopping_list(user_id, pending["title"], pending["items"])
                result = {
                    "status": "saved", "type": "save_shopping_list", "title": pending["title"],
                    "items": pending["items"], "list_id": list_id,
                }
                return {"action_result": result}

            recipe = pending["recipe"]
            recipe_id = await self.deps.save_recipe(user_id, recipe)
            result = {"status": "saved", "type": "save_recipe", "title": recipe["title"], "recipe_id": recipe_id}
            update: dict = {"action_result": result}
            if state.get("last_generated") and state["last_generated"].get("title") == recipe["title"]:
                update["last_generated"] = {**state["last_generated"], "id": recipe_id}
            update["last_shown"] = [
                {**c, "id": recipe_id} if c.get("title") == recipe["title"] and c.get("id") is None else c
                for c in state.get("last_shown", [])
            ]
            return update
        except Exception:
            logger.exception("save_pending_action failed")
            return {"action_result": {"status": "failed", "type": pending["type"]}}

    async def _compose_action(self, state: ChefState) -> dict:
        result = state.get("action_result") or {"status": "failed", "type": "unknown"}
        user_text = last_user_text(state.get("messages", []))
        language = state.get("language", "English")
        facts = {k: v for k, v in result.items() if k != "items"}
        if result.get("items"):
            facts["item_count"] = len(result["items"])
        payload = {
            "task": "action",
            "user_message": user_text,
            "reply_language": language,
            "action_result": facts,
        }
        try:
            text = await self.deps.llm.compose(payload)
            if result.get("status") == "saved" and result.get("items"):
                text = f"{text}\n\n{format_items(result['items'])}"
        except Exception:
            logger.exception("compose_answer (action): LLM failed, using fallback text")
            text = fallback_action_answer(result)
            if result.get("status") == "saved" and result.get("items"):
                text = f"{text}\n\n{format_items(result['items'])}"
        return {"answer": text, "messages": [AIMessage(content=text)]}
