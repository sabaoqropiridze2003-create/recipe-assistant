from collections import Counter

from app.services.allergens import compute_allergens
from app.services.safety import diet_claim_problems
from scripts.recipes_data import RECIPES


def _names(recipe):
    return [item[0] for item in recipe["ingredients"]]


def test_catalog_has_at_least_30_unique_recipes():
    titles = [r["title"] for r in RECIPES]
    assert len(titles) >= 30
    assert len(set(titles)) == len(titles)


def test_catalog_meets_diet_minimums():
    tags = Counter(t for r in RECIPES for t in r["diet_tags"])
    assert tags["vegetarian"] + tags["vegan"] >= 5
    assert tags["vegan"] >= 3
    assert tags["gluten_free"] >= 3


def test_catalog_covers_meal_types_and_allergens():
    meals = {r["meal_type"] for r in RECIPES}
    assert {"breakfast", "lunch", "dinner", "dessert"} <= meals
    allergens = {a for r in RECIPES for a in compute_allergens(_names(r))}
    assert {"dairy", "nuts", "gluten", "eggs", "seafood"} <= allergens


def test_catalog_diet_tags_match_ingredients():
    for recipe in RECIPES:
        assert diet_claim_problems(recipe["diet_tags"], _names(recipe)) == [], recipe["title"]