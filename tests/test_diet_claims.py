from app.services.allergens import compute_allergens
from app.services.safety import diet_claim_problems


def test_new_dictionary_words():
    assert compute_allergens(["spaghetti"]) == ["gluten"]
    assert compute_allergens(["mozzarella", "feta cheese"]) == ["dairy"]
    assert compute_allergens(["egg yolk"]) == ["eggs"]
    assert compute_allergens(["cod fillet"]) == ["seafood"]


def test_diet_claims_are_verified_by_code():
    assert diet_claim_problems(["vegan"], ["chicken breast", "rice"])
    assert diet_claim_problems(["vegan"], ["rice", "honey"])
    assert diet_claim_problems(["vegetarian"], ["anchovy fillets"])
    assert diet_claim_problems(["gluten_free"], ["spaghetti"])
    assert diet_claim_problems(["vegan"], ["tofu", "coconut milk"]) == []
    assert diet_claim_problems(["vegetarian", "gluten_free"], ["egg", "rice"]) == []