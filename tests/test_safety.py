from types import SimpleNamespace as NS

from app.services.allergens import compute_allergens
from app.services.pantry_match import names_match, pantry_match
from app.services.safety import filter_safe_recipes, safety_violations
from app.services.scaling import scale_quantity


def ing(name, is_staple=False):
    return NS(name=name, is_staple=is_staple)


def recipe(title, ingredient_names, allergens=None, diet_tags=None):
    return NS(
        title=title,
        ingredients=[ing(n) for n in ingredient_names],
        allergens=allergens or [],
        diet_tags=diet_tags or [],
    )


# ---- tests from the spec's list ----

def test_safety_filter_blocks_allergen():
    pancakes = recipe("Pancakes", ["flour", "milk", "egg"], allergens=["dairy", "eggs", "gluten"])
    salad = recipe("Salad", ["tomato", "cucumber"])
    result = filter_safe_recipes([pancakes, salad], allergies=["dairy"], diet="none", disliked=[])
    assert [r.title for r in result] == ["Salad"]


def test_safety_filter_diet():
    steak = recipe("Steak", ["beef", "salt"])
    tofu = recipe("Tofu bowl", ["tofu", "rice"], diet_tags=["vegan"])
    veggie = recipe("Omelette", ["egg", "spinach"], diet_tags=["vegetarian"])
    all_recipes = [steak, tofu, veggie]

    vegan = filter_safe_recipes(all_recipes, allergies=[], diet="vegan", disliked=[])
    assert [r.title for r in vegan] == ["Tofu bowl"]

    vegetarian = filter_safe_recipes(all_recipes, allergies=[], diet="vegetarian", disliked=[])
    assert [r.title for r in vegetarian] == ["Tofu bowl", "Omelette"]

    anything = filter_safe_recipes(all_recipes, allergies=[], diet="none", disliked=[])
    assert len(anything) == 3


def test_generated_recipe_allergens_by_code():
    names = ["Chicken breast", "Butter", "wheat flour", "Cashews"]
    assert compute_allergens(names) == ["dairy", "gluten", "nuts"]

    violations = safety_violations(
        allergies=["dairy"], diet="none", disliked=[],
        ingredient_names=names, allergens=[], diet_tags=[],
    )
    assert violations == ["allergen: dairy"]


def test_pantry_match_score():
    ingredients = [ing("chicken breast"), ing("rice"), ing("broccoli"), ing("salt", is_staple=True)]
    result = pantry_match(ingredients, ["Chicken", "rice"])
    assert result.score == 0.67          
    assert result.have == ["chicken breast", "rice"]
    assert result.missing == ["broccoli"]


def test_scale_recipe():
    assert scale_quantity(200, base_servings=2, target_servings=6) == 600
    assert scale_quantity(1, base_servings=4, target_servings=2) == 0.5


# ---- extra tests for the decisions we made ----

def test_stored_allergens_empty_but_ingredients_contain_allergen():
    old = recipe("Old recipe", ["butter", "rice"], allergens=[])
    assert filter_safe_recipes([old], allergies=["dairy"], diet="none", disliked=[]) == []


def test_obvious_false_alarms_are_not_flagged():
    assert compute_allergens(["eggplant", "butternut squash", "coconut milk"]) == []


def test_allergy_outside_dictionary_scans_ingredients():
    kiwi = recipe("Fruit bowl", ["kiwi fruit", "apple"])
    assert filter_safe_recipes([kiwi], allergies=["Kiwi"], diet="none", disliked=[]) == []


def test_user_allergic_to_eggplant_is_protected():
    dish = recipe("Moussaka", ["eggplant", "tomato"])
    assert filter_safe_recipes([dish], allergies=["eggplant"], diet="none", disliked=[]) == []


def test_allergy_aliases():
    dish = recipe("Latte cake", ["milk", "sugar"])
    assert filter_safe_recipes([dish], allergies=["Lactose"], diet="none", disliked=[]) == []


def test_disliked_ingredient_is_filtered():
    dish = recipe("Soup", ["Mushrooms", "onion"])
    assert filter_safe_recipes([dish], allergies=[], diet="none", disliked=["mushroom"]) == []


def test_unknown_diet_fails_closed():
    dish = recipe("Salad", ["tomato"], diet_tags=["vegan"])
    assert filter_safe_recipes([dish], allergies=[], diet="keto", disliked=[]) == []


def test_pantry_edge_cases():
    only_staples = [ing("salt", is_staple=True), ing("oil", is_staple=True)]
    assert pantry_match(only_staples, []).score == 1.0
    assert pantry_match([ing("rice")], []).score == 0.0


def test_names_match():
    assert names_match("tomatoes", "tomato")
    assert names_match("chicken breast", "chicken")
    assert not names_match("milk", "rice")