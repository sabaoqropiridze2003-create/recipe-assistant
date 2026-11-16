import re

from app.services.normalize import normalize_name


ALLERGEN_KEYWORDS: dict[str, list[str]] = {
    "dairy": [
        "milk", "cheese", "butter", "cream", "yogurt", "yoghurt", "ghee", "whey",
        "რძე", "რძის", "ყველი", "კარაქი", "მაწონი", "არაჟანი",
    ],
    "nuts": [
        "almond", "walnut", "hazelnut", "cashew", "pistachio", "pecan", "peanut",
        "ნიგოზი", "თხილი", "ნუში",
    ],
    "gluten": [
        "wheat", "flour", "bread", "pasta", "noodle", "couscous", "semolina", "barley", "rye",
        "ფქვილი", "პური", "მაკარონი",
    ],
    "eggs": ["egg", "mayonnaise", "კვერცხი"],
    "seafood": [
        "shrimp", "fish", "salmon", "tuna", "crab", "lobster", "prawn", "squid", "anchovy",
        "თევზი", "კრევეტი",
    ],
}


ALLERGY_ALIASES = {
    "lactose": "dairy", "milk": "dairy",
    "nut": "nuts", "tree nuts": "nuts", "peanut": "nuts", "peanuts": "nuts",
    "wheat": "gluten", "egg": "eggs",
    "fish": "seafood", "shellfish": "seafood",
}


_SAFE_PHRASES = ("eggplant", "butternut", "coconut milk", "coconut cream", "cocoa butter")


def _starts_word(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}", text) is not None


def compute_allergens(ingredient_names: list[str]) -> list[str]:
    found: set[str] = set()
    for name in ingredient_names:
        text = normalize_name(name)
        for phrase in _SAFE_PHRASES:
            text = text.replace(phrase, " ")
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if any(_starts_word(text, k) for k in keywords):
                found.add(allergen)
    return sorted(found)


def canonical_allergy(term: str) -> str:
    term = normalize_name(term)
    return ALLERGY_ALIASES.get(term, term)


def mentions_term(ingredient_names: list[str], term: str) -> bool:
    term = normalize_name(term)
    return any(_starts_word(normalize_name(n), term) for n in ingredient_names)