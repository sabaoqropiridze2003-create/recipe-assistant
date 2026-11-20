from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import require_admin
from app.schemas.analytics import AiGeneratedStats, IntentCount, PopularRecipes, RecipeCount


router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_admin)]
)


MOST_SHOWN_SQL = text(
    """
    SELECT r.id AS recipe_id, r.title, COUNT(*) AS times
    FROM chat_messages m
    CROSS JOIN LATERAL unnest(m.recipe_ids) AS shown(recipe_id)
    JOIN recipes r ON r.id = shown.recipe_id
    WHERE m.role = 'assistant'
    GROUP BY r.id, r.title
    ORDER BY times DESC, r.title
    LIMIT :limit
    """
)

MOST_SAVED_SQL = text(
    """
    SELECT r.id AS recipe_id, r.title, COUNT(*) AS times
    FROM saved_recipes s
    JOIN recipes r ON r.id = s.recipe_id
    GROUP BY r.id, r.title
    ORDER BY times DESC, r.title
    LIMIT :limit
    """
)

AI_STATS_SQL = text(
    """
    SELECT
        (SELECT COUNT(*) FROM chat_messages WHERE role = 'assistant' AND ai_generated) AS created,
        (SELECT COUNT(*) FROM recipes WHERE source = 'ai_generated') AS saved,
        (SELECT COUNT(*) FROM saved_recipes s JOIN recipes r ON r.id = s.recipe_id
            WHERE r.source = 'ai_generated') AS in_cookbooks
    """
)

INTENTS_SQL = text(
    """
    SELECT intent, COUNT(*) AS count
    FROM chat_messages
    WHERE role = 'assistant' AND intent IS NOT NULL
    GROUP BY intent
    ORDER BY count DESC, intent
    """
)


@router.get("/popular-recipes", response_model=PopularRecipes)
async def popular_recipes(
    limit: int = Query(default=10, ge=1, le=50), db: AsyncSession = Depends(get_db)
):
    shown = (await db.execute(MOST_SHOWN_SQL, {"limit": limit})).mappings().all()
    saved = (await db.execute(MOST_SAVED_SQL, {"limit": limit})).mappings().all()
    return PopularRecipes(
        most_shown=[RecipeCount(**row) for row in shown],
        most_saved=[RecipeCount(**row) for row in saved],
    )


@router.get("/ai-generated", response_model=AiGeneratedStats)
async def ai_generated(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(AI_STATS_SQL)).mappings().one()
    created, saved = row["created"], row["saved"]
    return AiGeneratedStats(
        created=created,
        saved=saved,
        in_cookbooks=row["in_cookbooks"],
        save_rate=round(saved / created, 2) if created else None,
    )


@router.get("/intents", response_model=list[IntentCount])
async def intents(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(INTENTS_SQL)).mappings().all()
    return [IntentCount(**row) for row in rows]
