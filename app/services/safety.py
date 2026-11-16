from app.services.allergens import (
    ALLERGEN_KEYWORDS,
    canonical_allergy,
    compute_allergens,
    mentions_term,
)
from app.services.normalize import clean_list


def diet_ok(diet: str | None, diet_tags: list[str]) -> bool:
    if diet in (None, "none"):
        return True
    if diet == "vegan":
        return "vegan" in diet_tags
    if diet == "vegetarian":
        return "vegetarian" in diet_tags or "vegan" in diet_tags
    return False  


def safety_violations(
    *,
    allergies: list[str],
    diet: str | None,
    disliked: list[str],
    ingredient_names: list[str],
    allergens: list[str],
    diet_tags: list[str],
) -> list[str]:
    """Return the reasons a recipe is NOT safe. Empty list means safe."""
    violations: list[str] = []

    effective = set(allergens) | set(compute_allergens(ingredient_names))

    for allergy in clean_list(allergies):
        category = canonical_allergy(allergy)
        if category in ALLERGEN_KEYWORDS:
            if category in effective:
                violations.append(f"allergen: {category}")
        elif mentions_term(ingredient_names, category):
            violations.append(f"allergen: {category}")

    for term in clean_list(disliked):
        if mentions_term(ingredient_names, term):
            violations.append(f"disliked: {term}")

    if not diet_ok(diet, diet_tags):
        violations.append(f"diet: {diet}")

    return violations


def filter_safe_recipes(recipes, *, allergies, diet, disliked):
    """Keep only recipes with no violations. Works on any object that has
    .ingredients (with .name), .allergens and .diet_tags."""
    return [
        r
        for r in recipes
        if not safety_violations(
            allergies=allergies,
            diet=diet,
            disliked=disliked,
            ingredient_names=[i.name for i in r.ingredients],
            allergens=r.allergens,
            diet_tags=r.diet_tags,
        )
    ]