from app.services.allergens import (
    ALLERGEN_KEYWORDS,
    canonical_allergy,
    compute_allergens,
    mentions_term,
)
from app.services.normalize import clean_list

MEAT_KEYWORDS = [
    "chicken", "beef", "pork", "lamb", "veal", "turkey", "duck", "bacon", "ham", "sausage",
    "mince", "meat", "gelatin", "lard",
    "ქათამი", "ღორის", "საქონლის", "ცხვრის",
]
NON_VEGAN_EXTRAS = ["honey", "gelatin"]


def diet_ok(diet: str | None, diet_tags: list[str]) -> bool:
    if diet in (None, "none"):
        return True
    if diet == "vegan":
        return "vegan" in diet_tags
    if diet == "vegetarian":
        return "vegetarian" in diet_tags or "vegan" in diet_tags
    return False

def diet_claim_problems(diet_tags: list[str], ingredient_names: list[str]) -> list[str]:
    """Check that the diet tags a recipe CLAIMS are consistent with its ingredients."""
    problems: list[str] = []
    allergens = set(compute_allergens(ingredient_names))
    has_meat = "seafood" in allergens or any(
        mentions_term(ingredient_names, w) for w in MEAT_KEYWORDS
    )

    if ("vegetarian" in diet_tags or "vegan" in diet_tags) and has_meat:
        problems.append("tagged vegetarian/vegan but contains meat or fish")
    if "vegan" in diet_tags:
        if allergens & {"dairy", "eggs"}:
            problems.append("tagged vegan but contains dairy or eggs")
        if any(mentions_term(ingredient_names, w) for w in NON_VEGAN_EXTRAS):
            problems.append("tagged vegan but contains honey or gelatin")
    if "gluten_free" in diet_tags and "gluten" in allergens:
        problems.append("tagged gluten_free but contains gluten")
    return problems  


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