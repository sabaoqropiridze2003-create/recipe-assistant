from sqlalchemy import or_

from app.db.models import Recipe


def visible_to(user_id: int):
    """A user sees the shared catalog plus recipes they own (e.g. their AI-generated ones)."""
    return or_(Recipe.source == "catalog", Recipe.owner_id == user_id)