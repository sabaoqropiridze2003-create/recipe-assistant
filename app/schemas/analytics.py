from pydantic import BaseModel


class RecipeCount(BaseModel):
    recipe_id: int
    title: str
    times: int


class PopularRecipes(BaseModel):
    most_shown: list[RecipeCount]  
    most_saved: list[RecipeCount]  


class AiGeneratedStats(BaseModel):
    created: int  
    saved: int  
    in_cookbooks: int  
    save_rate: float | None  


class IntentCount(BaseModel):
    intent: str
    count: int
