from app.graph.logic import (
    build_shopping_items,
    describe_pending,
    format_items,
    parse_confirmation,
    pick_recipes,
    route_after_confirm,
    route_after_prepare,
    sanitize_constraints,
    sanitize_items,
    shopping_title,
)


def recipe(id, title, ingredients):
    return {
        "id": id, "title": title,
        "ingredients": [
            {"name": n, "quantity": q, "unit": u, "is_staple": staple}
            for n, q, u, staple in ingredients
        ],
    }


SOUP = recipe(7, "Soup", [("carrot", 200, "g", False), ("onion", 2, "pcs", False), ("salt", 1, "tsp", True)])


# ---- what to buy is computed by code ----

def test_shopping_list_is_recipe_minus_pantry():
    pantry = [{"name": "carrot", "quantity": 50, "unit": "g"}]
    items = build_shopping_items([SOUP], pantry)
    assert items == [
        {"name": "carrot", "quantity": 150.0, "unit": "g", "recipe_id": 7},
        {"name": "onion", "quantity": 2.0, "unit": "pcs", "recipe_id": 7},
    ]  


def test_enough_in_the_pantry_means_nothing_to_buy():
    pantry = [{"name": "carrots", "quantity": 500, "unit": "g"}, {"name": "onion", "quantity": 3, "unit": "pcs"}]
    assert build_shopping_items([SOUP], pantry) == []


def test_pantry_item_with_unknown_amount_counts_as_enough():
    pantry = [{"name": "carrot", "quantity": None, "unit": None}]
    assert [i["name"] for i in build_shopping_items([SOUP], pantry)] == ["onion"]


def test_different_units_are_never_converted_by_guessing():
    pantry = [{"name": "carrot", "quantity": 1, "unit": "kg"}]  
    assert build_shopping_items([SOUP], pantry)[0] == {
        "name": "carrot", "quantity": 200.0, "unit": "g", "recipe_id": 7,
    }


def test_the_same_ingredient_from_two_recipes_is_added_up():
    stew = recipe(8, "Stew", [("onion", 1, "pcs", False), ("potato", 3, "pcs", False)])
    items = {i["name"]: i for i in build_shopping_items([SOUP, stew], [])}
    assert items["onion"]["quantity"] == 3.0 and items["onion"]["recipe_id"] is None  
    assert items["potato"]["recipe_id"] == 8


def test_shopping_title():
    assert shopping_title([SOUP]) == "Shopping list: Soup"
    assert shopping_title([SOUP, SOUP]) == "Shopping list (2 recipes)"


# ---- choosing the recipes ----

def test_pick_recipes():
    shown = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert pick_recipes(shown, 2, False) == [{"id": 2}]
    assert pick_recipes(shown, None, True) == shown
    assert pick_recipes(shown, None, False) == []  
    assert pick_recipes([], 1, True) == []


# ---- the confirmation answer is never trusted ----

def test_only_an_explicit_true_approves():
    assert parse_confirmation({"approved": True}) == (True, None)
    assert parse_confirmation({"approved": "yes"}) == (False, None)
    assert parse_confirmation({"approved": 1}) == (False, None)
    assert parse_confirmation({}) == (False, None)
    assert parse_confirmation("approve") == (False, None)
    assert parse_confirmation(None) == (False, None)
    assert parse_confirmation(True) == (True, None)
    assert parse_confirmation({"approved": True, "items": [1]}) == (True, [1])


def test_edited_items_are_cleaned():
    original = [{"name": "carrot", "quantity": 150.0, "unit": "g", "recipe_id": 7}]
    raw = [
        {"name": " Carrot ", "quantity": "300", "unit": "G", "recipe_id": 999},  
        {"name": "carrot", "quantity": 5, "unit": "g"}, 
        {"name": "ghost", "quantity": -2, "unit": "g"},  
        {"name": "milk", "quantity": "lots", "unit": "l"},  
        {"name": "", "quantity": 1, "unit": "g"},  
        {"name": "bread", "quantity": None, "unit": ""},  
        "not a dict",
    ]
    assert sanitize_items(raw, original) == [
        {"name": "carrot", "quantity": 300.0, "unit": "g", "recipe_id": 7},
        {"name": "bread", "quantity": None, "unit": None, "recipe_id": None},
    ]
    assert sanitize_items("not a list", original) == []
    assert len(sanitize_items([{"name": f"item{i}", "quantity": 1, "unit": "g"} for i in range(500)], [])) == 100


def test_routing_around_the_confirmation():
    assert route_after_prepare({"pending_action": {"type": "save_shopping_list"}}) == "confirm"
    assert route_after_prepare({"pending_action": None}) == "compose"
    assert route_after_confirm({"confirmed": True}) == "save"
    assert route_after_confirm({"confirmed": False}) == "compose"
    assert route_after_confirm({}) == "compose"  


def test_what_the_user_sees_at_the_confirmation_step():
    pending = {"type": "save_shopping_list", "title": "Shopping list: Soup",
               "items": [{"name": "carrot", "quantity": 150.0, "unit": "g", "recipe_id": 7}]}
    shown = describe_pending(pending)
    assert shown == {"type": "confirmation_required", "action": "save_shopping_list",
                     "title": "Shopping list: Soup",
                     "items": [{"name": "carrot", "quantity": 150.0, "unit": "g"}]}  
    recipe_shown = describe_pending({"type": "save_recipe", "recipe": {"title": "Pudding", "source": "ai_generated"}})
    assert recipe_shown["ai_generated"] is True and recipe_shown["title"] == "Pudding"


def test_item_lines():
    items = [{"name": "carrot", "quantity": 150.0, "unit": "g"}, {"name": "bread", "quantity": None, "unit": None}]
    assert format_items(items) == "- 150 g carrot\n- bread"


def test_all_shown_flag_is_cleaned():
    assert sanitize_constraints({"all_shown": True})["all_shown"] is True
    assert sanitize_constraints({"all_shown": "yes"})["all_shown"] is False
    assert sanitize_constraints({})["all_shown"] is False
