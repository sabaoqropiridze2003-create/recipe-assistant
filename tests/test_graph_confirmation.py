from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.builder import build_chef_graph
from app.graph.deps import ChefDeps


def make_recipe(id, title, ingredients, servings=2):
    return {
        "id": id, "title": title, "description": "", "cuisine": "test", "meal_type": "dinner",
        "servings": servings, "total_time_min": 20, "diet_tags": [], "allergens": [],
        "source": "catalog", "distance": 0.2,
        "ingredients": [
            {"name": n, "quantity": q, "unit": u, "is_staple": staple} for n, q, u, staple in ingredients
        ],
    }


SOUP = make_recipe(7, "Soup", [("carrot", 200, "g", False), ("onion", 2, "pcs", False), ("salt", 1, "tsp", True)])
STEW = make_recipe(8, "Stew", [("onion", 1, "pcs", False), ("potato", 3, "pcs", False)])
CARDS = [{"id": 7, "title": "Soup", "servings": 2}, {"id": 8, "title": "Stew", "servings": 2}]


def analysis(intent, **constraints):
    base = {
        "ingredients": [], "exclude_ingredients": [], "max_time_min": None, "servings": None,
        "cuisine": None, "meal_type": None, "diet": None,
    }
    base.update(constraints)
    return {"intent": intent, "constraints": base, "refers_to_previous": False}


class FakeLLM:
    def __init__(self, *results, text="FAKE ANSWER"):
        self.results = list(results)  
        self.text = text
        self.payloads = []

    async def analyze(self, history):
        return self.results.pop(0)

    async def compose(self, payload):
        self.payloads.append(payload)
        return self.text


def make_graph(llm, *, pantry=None, recipes=None, search_results=None, fail_save=False):
    """Fake database functions that RECORD what would have been written."""
    saved = {"lists": [], "recipes": []}
    by_id = {r["id"]: r for r in (recipes or [SOUP, STEW])}

    async def load_context(user_id):
        return {"allergies": [], "diet": "none", "disliked_ingredients": [], "default_servings": 2}, []

    async def search(user_id, constraints, query):
        return search_results or []

    async def get_recipe(user_id, recipe_id):
        return by_id.get(recipe_id)

    async def get_pantry(user_id):
        return pantry or []

    async def save_shopping_list(user_id, title, items):
        if fail_save:
            raise RuntimeError("database is down")
        saved["lists"].append((user_id, title, items))
        return 41

    async def save_recipe(user_id, recipe):
        if fail_save:
            raise RuntimeError("database is down")
        saved["recipes"].append((user_id, recipe))
        return 77

    deps = ChefDeps(
        llm=llm, load_context=load_context, search=search, get_recipe=get_recipe,
        get_pantry=get_pantry, save_shopping_list=save_shopping_list, save_recipe=save_recipe,
    )
    return build_chef_graph(deps, InMemorySaver()), saved


def config(thread="chat-1"):
    return {"configurable": {"thread_id": thread}}


async def say(graph, text, thread="chat-1", **extra_state):
    state = {"messages": [HumanMessage(content=text)], "user_id": 1, **extra_state}
    return await graph.ainvoke(state, config(thread))


async def resume(graph, answer, thread="chat-1"):
    return await graph.ainvoke(Command(resume=answer), config(thread))


PANTRY = [{"name": "carrot", "quantity": 50, "unit": "g"}]


# ---- tests from the spec's list ----

async def test_shopping_list_requires_confirmation():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm, pantry=PANTRY)

    paused = await say(graph, "what do I need to buy for the first one?", last_shown=CARDS)
    shown = paused["__interrupt__"][0].value
    assert shown["action"] == "save_shopping_list"
    assert shown["items"] == [
        {"name": "carrot", "quantity": 150.0, "unit": "g"},
        {"name": "onion", "quantity": 2.0, "unit": "pcs"},
    ]
    assert saved["lists"] == []  

    done = await resume(graph, {"approved": True})
    assert saved["lists"] == [(1, "Shopping list: Soup", [
        {"name": "carrot", "quantity": 150.0, "unit": "g", "recipe_id": 7},
        {"name": "onion", "quantity": 2.0, "unit": "pcs", "recipe_id": 7},
    ])]
    assert "- 150 g carrot" in done["answer"]  


async def test_declining_writes_nothing():
    llm = FakeLLM(analysis("shopping_list", reference_index=1), text="Okay, nothing saved.")
    graph, saved = make_graph(llm, pantry=PANTRY)
    await say(graph, "shopping list for the first one", last_shown=CARDS)
    done = await resume(graph, {"approved": False})
    assert saved["lists"] == [] and done["confirmed"] is False
    assert llm.payloads[-1]["action_result"]["status"] == "declined"


async def test_interrupt_and_resume():
    llm = FakeLLM(analysis("shopping_list", reference_index=2))
    graph, _ = make_graph(llm)
    paused = await say(graph, "what do I buy for the second one?", last_shown=CARDS)
    assert "__interrupt__" in paused and not paused.get("answer")  
    done = await resume(graph, {"approved": True})
    assert "__interrupt__" not in done  
    assert done["confirmed"] is True and done["answer"]


# ---- extra tests: the confirmation answer is never trusted ----

async def test_edited_list_is_cleaned_and_saved_instead():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm, pantry=PANTRY)
    await say(graph, "shopping list", last_shown=CARDS)
    edited = [
        {"name": " Carrot ", "quantity": 300, "unit": "G"},
        {"name": "bad", "quantity": -1, "unit": "g"},
        {"name": "bread", "quantity": 1, "unit": "pcs"},
    ]
    await resume(graph, {"approved": True, "items": edited})
    _, _, items = saved["lists"][0]
    assert items == [
        {"name": "carrot", "quantity": 300.0, "unit": "g", "recipe_id": 7},
        {"name": "bread", "quantity": 1.0, "unit": "pcs", "recipe_id": None},
    ]


async def test_emptying_the_list_counts_as_cancelling():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm)
    await say(graph, "shopping list", last_shown=CARDS)
    await resume(graph, {"approved": True, "items": []})
    assert saved["lists"] == []


async def test_the_client_cannot_change_the_user_or_the_title():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm)
    await say(graph, "shopping list", last_shown=CARDS)
    await resume(graph, {"approved": True, "user_id": 99, "title": "hacked", "list_id": 5})
    user_id, title, _ = saved["lists"][0]
    assert user_id == 1 and title == "Shopping list: Soup"


async def test_a_vague_answer_does_not_approve():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm)
    await say(graph, "shopping list", last_shown=CARDS)
    await resume(graph, {"approved": "yes please"})  
    assert saved["lists"] == []


# ---- extra tests: cases without a confirmation ----

async def test_nothing_to_buy_needs_no_confirmation():
    pantry = [{"name": "carrot", "quantity": 500, "unit": "g"}, {"name": "onion", "quantity": None, "unit": None}]
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm, pantry=pantry)
    state = await say(graph, "what do I need to buy?", last_shown=CARDS)
    assert "__interrupt__" not in state and saved["lists"] == []
    assert llm.payloads[-1]["action_result"]["status"] == "nothing_to_buy"


async def test_the_assistant_asks_which_recipe_when_it_is_unclear():
    llm = FakeLLM(analysis("shopping_list"))  
    graph, saved = make_graph(llm)
    state = await say(graph, "what do I need to buy?", last_shown=CARDS)
    assert "__interrupt__" not in state and saved["lists"] == []
    assert llm.payloads[-1]["action_result"] == {
        "status": "clarify", "reason": "which_recipe", "options": ["Soup", "Stew"],
    }


async def test_all_shown_recipes_are_combined_into_one_list():
    llm = FakeLLM(analysis("shopping_list", all_shown=True))
    graph, _ = make_graph(llm)
    paused = await say(graph, "shopping list for all of them", last_shown=CARDS)
    items = {i["name"]: i for i in paused["__interrupt__"][0].value["items"]}
    assert items["onion"]["quantity"] == 3.0  
    assert paused["__interrupt__"][0].value["title"] == "Shopping list (2 recipes)"


async def test_a_database_error_is_reported_and_nothing_crashes():
    llm = FakeLLM(analysis("shopping_list", reference_index=1))
    graph, _ = make_graph(llm, fail_save=True)
    await say(graph, "shopping list", last_shown=CARDS)
    done = await resume(graph, {"approved": True})
    assert llm.payloads[-1]["action_result"]["status"] == "failed"
    assert done["answer"]


# ---- saving a recipe to the cookbook ----

AI_RECIPE = {
    "id": None, "title": "Pudding", "description": "", "cuisine": None, "meal_type": "dessert",
    "servings": 2, "total_time_min": 10, "diet_tags": ["vegan"], "allergens": [], "source": "ai_generated",
    "ingredients": [{"name": "banana", "quantity": 2, "unit": "pcs", "is_staple": False}],
    "steps": ["Blend.", "Chill."],
}


async def test_saving_an_ai_recipe_needs_confirmation_and_uses_the_server_copy():
    llm = FakeLLM(analysis("save_recipe"))
    graph, saved = make_graph(llm)
    paused = await say(
        graph, "save this one", last_shown=[{"id": None, "title": "Pudding", "servings": 2}],
        last_generated=AI_RECIPE,
    )
    shown = paused["__interrupt__"][0].value
    assert shown["action"] == "save_recipe" and shown["ai_generated"] is True
    assert saved["recipes"] == []  

    evil = {"title": "evil", "ingredients": []}
    done = await resume(graph, {"approved": True, "recipe": evil})  
    user_id, recipe = saved["recipes"][0]
    assert user_id == 1 and recipe["title"] == "Pudding" and recipe["steps"] == ["Blend.", "Chill."]
    assert done["last_generated"]["id"] == 77  
    assert done["last_shown"][0]["id"] == 77


async def test_saving_a_catalog_recipe_goes_through_the_same_confirmation():
    llm = FakeLLM(analysis("save_recipe", reference_index=2))
    graph, saved = make_graph(llm)
    paused = await say(graph, "save the second one", last_shown=CARDS)
    assert paused["__interrupt__"][0].value["ai_generated"] is False
    await resume(graph, {"approved": True})
    assert saved["recipes"][0][1]["id"] == 8


async def test_declining_to_save_a_recipe_writes_nothing():
    llm = FakeLLM(analysis("save_recipe", reference_index=1))
    graph, saved = make_graph(llm)
    await say(graph, "save the first one", last_shown=CARDS)
    await resume(graph, {"approved": False})
    assert saved["recipes"] == []


# ---- conversation memory and a clean slate per message ----

async def test_the_second_message_remembers_what_the_first_one_showed():
    recipe = make_recipe(7, "Soup", [("carrot", 100, "g", False), ("onion", 1, "pcs", False)])
    llm = FakeLLM(
        analysis("find_recipe"),
        analysis("cooking_help", cooking_task="scale", servings=6, reference_index=1),
    )
    graph, _ = make_graph(llm, search_results=[recipe], recipes=[recipe])
    first = await say(graph, "show me a soup")
    assert [c["title"] for c in first["cards"]] == ["Soup"]
    second = await say(graph, "make the first one for 6")  
    assert second["helper_result"]["kind"] == "scale"
    assert second["helper_result"]["ingredients"][0]["quantity"] == 300


async def test_a_new_message_clears_the_old_confirmation():
    llm = FakeLLM(analysis("shopping_list", reference_index=1), analysis("find_recipe"))
    graph, _ = make_graph(llm, search_results=[SOUP])
    await say(graph, "shopping list", last_shown=CARDS)
    await resume(graph, {"approved": True})
    later = await say(graph, "show me something else")
    assert later["pending_action"] is None and later["action_result"] is None
    assert later["confirmed"] is None


async def test_two_chats_do_not_mix():
    llm = FakeLLM(analysis("shopping_list", reference_index=1), analysis("shopping_list", reference_index=1))
    graph, saved = make_graph(llm)
    await say(graph, "shopping list", thread="chat-1", last_shown=[CARDS[0]])
    await say(graph, "shopping list", thread="chat-2", last_shown=[CARDS[1]])
    await resume(graph, {"approved": True}, thread="chat-1")
    assert [title for _, title, _ in saved["lists"]] == ["Shopping list: Soup"]  
