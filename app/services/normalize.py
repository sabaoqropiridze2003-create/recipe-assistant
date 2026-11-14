def normalize_name(name: str) -> str:
    """lowercase, trim, collapse repeated spaces: '  Chicken   Breast ' -> 'chicken breast'"""
    return " ".join(name.strip().lower().split())


def clean_list(values: list[str]) -> list[str]:
    """normalize every item, drop empties and duplicates, keep order"""
    result: list[str] = []
    for value in values:
        value = normalize_name(value)
        if value and value not in result:
            result.append(value)
    return result