from dataclasses import dataclass

from app.services.normalize import normalize_name


def _stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("oes") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _tokens(name: str) -> set[str]:
    return {_stem(t) for t in normalize_name(name).split()}


def names_match(a: str, b: str) -> bool:
    """'chicken breast' ~ 'chicken', 'tomatoes' ~ 'tomato': one name's words contain the other's."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


@dataclass(frozen=True)
class PantryMatch:
    score: float
    have: list[str]
    missing: list[str]


def pantry_match(ingredients, pantry_names: list[str]) -> PantryMatch:
    """score = non-staple ingredients we have / all non-staple ingredients."""
    needed = [i for i in ingredients if not i.is_staple]
    if not needed:
        return PantryMatch(1.0, [], [])

    have: list[str] = []
    missing: list[str] = []
    for ingredient in needed:
        if any(names_match(ingredient.name, p) for p in pantry_names):
            have.append(ingredient.name)
        else:
            missing.append(ingredient.name)
    return PantryMatch(round(len(have) / len(needed), 2), have, missing)