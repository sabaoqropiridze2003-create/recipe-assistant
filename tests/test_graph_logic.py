import inspect
from types import SimpleNamespace as NS

from app.graph.logic import (
    MAX_RELAX,
    build_cards,
    rank_candidates,
    relax,
    route_after_safety,
    sanitize_constraints,
    stricter_diet,
    to_history,
)


def make_recipe(id, title, names, allergens=None):
    return {
        "id": id,
        "title": title,
        "description": "",
        "servings": 2,
        "total_time_min": 20,
        "allergens": allergens or [],
        "source": "catalog",
        "distance": 0.3,
        "ingredients": [
            {"name": n, "quantity": 1, "unit": "pcs", "is_staple": False} for n in names
        ],
    }




def test_relax_never_touches_allergies():
    constraints = {
        "ingredients": ["chicken"], "exclude_ingredients": ["dairy"], "max_time_min": 30,
        "servings": 4, "cuisine": "georgian", "meal_type": "dinner", "diet": "vegan",
        "min_overlap": 1,
    }

    assert list(inspect.signature(relax).parameters) == ["constraints", "attempt"]

    first = relax(constraints, 0)
    second = relax(first, 1)
    for relaxed in (first, second):
        assert relaxed["exclude_ingredients"] == ["dairy"]  
        assert relaxed["diet"] == "vegan"
        assert relaxed["meal_type"] == "dinner"
        assert relaxed["servings"] == 4
        assert "allergies" not in relaxed


def test_relax_loop_limit():
    unsafe = {"safe_recipes": []}
    assert route_after_safety({**unsafe, "relax_attempts": 0}) == "relax"
    assert route_after_safety({**unsafe, "relax_attempts": MAX_RELAX - 1}) == "relax"
    assert route_after_safety({**unsafe, "relax_attempts": MAX_RELAX}) == "generate"
    assert route_after_safety({"safe_recipes": [{"id": 1}], "relax_attempts": 0}) == "compose"




def test_relax_steps_in_order():
    base = {"cuisine": "georgian", "max_time_min": 30, "min_overlap": 1}
    first = relax(base, 0)
    assert first["cuisine"] is None and first["max_time_min"] == 45 and first["min_overlap"] == 1
    second = relax(first, 1)
    assert second["min_overlap"] == 0


def test_relax_skips_a_step_that_would_change_nothing():
    assert relax({"cuisine": None, "max_time_min": None, "min_overlap": 1}, 0)["min_overlap"] == 0


def test_sanitize_constraints_clamps_and_cleans():
    raw = {
        "ingredients": [" Chicken ", "chicken", "RICE", ""],
        "exclude_ingredients": None,
        "max_time_min": 9999,
        "servings": -3,
        "cuisine": " Georgian ",
        "meal_type": "Brunch",
        "diet": "keto",
    }
    clean = sanitize_constraints(raw)
    assert clean["ingredients"] == ["chicken", "rice"]
    assert clean["exclude_ingredients"] == []
    assert clean["max_time_min"] is None
    assert clean["servings"] is None
    assert clean["cuisine"] == "georgian"
    assert clean["meal_type"] is None
    assert clean["diet"] is None
    assert clean["min_overlap"] == 1
    ok = sanitize_constraints({"max_time_min": "30", "meal_type": "DINNER", "diet": "Vegan"})
    assert ok["max_time_min"] == 30 and ok["meal_type"] == "dinner" and ok["diet"] == "vegan"
    assert ok["min_overlap"] == 0


def test_request_diet_can_only_tighten():
    assert stricter_diet("none", "vegan") == "vegan"
    assert stricter_diet("vegan", None) == "vegan"
    assert stricter_diet("vegan", "vegetarian") == "vegan"
    assert stricter_diet("vegetarian", "vegan") == "vegan"
    assert stricter_diet("none", None) == "none"
    assert stricter_diet("keto", "vegan") == "keto"  


def test_rank_candidates_overlap_and_pantry_score():
    bowl = make_recipe(1, "Bowl", ["chicken breast", "rice", "broccoli", "garlic"])
    mousse = make_recipe(2, "Mousse", ["avocado", "cocoa powder"])
    kwargs = dict(available=["chicken", "rice"], mentioned=["chicken", "rice"])

    strict = rank_candidates([mousse, bowl], min_overlap=1, **kwargs)
    assert [r["title"] for r in strict] == ["Bowl"]
    assert strict[0]["match_score"] == 0.5
    assert strict[0]["missing"] == ["broccoli", "garlic"]

    loose = rank_candidates([mousse, bowl], min_overlap=0, **kwargs)
    assert [r["title"] for r in loose] == ["Bowl", "Mousse"]


def test_history_is_limited_in_length_and_size():
    messages = [NS(type="human" if i % 2 == 0 else "ai", content="x" * 2000) for i in range(15)]
    history = to_history(messages)
    assert len(history) == 10
    assert all(len(text) <= 1000 for _, text in history)
    assert history[-1][0] == "user"  


def test_cards_are_limited_and_allergens_recomputed():
    recipes = [make_recipe(i, f"R{i}", ["butter", "rice"], allergens=[]) for i in range(5)]
    cards = build_cards(recipes)
    assert len(cards) == 3
    assert cards[0]["allergens"] == ["dairy"]
