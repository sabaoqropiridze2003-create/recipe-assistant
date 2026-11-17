from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChefState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]  
    user_id: int  

    intent: str  
    refers_to_previous: bool
    constraints: dict

    profile: dict  
    pantry: list[str]

    candidates: list[dict]
    safe_recipes: list[dict]
    blocked_summary: dict  
    relax_attempts: int
    generated_recipe: dict | None

    pending_action: dict | None
    confirmed: bool | None

    cards: list[dict]  
    last_shown: list[dict]  
    answer: str