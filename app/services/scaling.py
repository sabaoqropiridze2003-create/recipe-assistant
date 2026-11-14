def scale_quantity(quantity: float, base_servings: int, target_servings: int) -> float:
    return round(quantity * target_servings / base_servings, 2)