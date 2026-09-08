from fastapi import APIRouter, Depends, HTTPException, Form, BackgroundTasks
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import Optional
import uuid

from app.core.database import get_db
from app.routes.deps import get_current_user
from app.services.presentation.telegram_sender import send_status_message
from app.services.article.pipeline import ArticlePipeline

router = APIRouter(prefix="/articles", tags=["Articles"])

async def run_article_pipeline_background(
    pipeline: ArticlePipeline,
    topic: str,
    author: str,
    language: str,
    telegram_id: Optional[int]
):
    try:
        await pipeline.run(
            topic=topic,
            author=author,
            language=language,
            telegram_id=telegram_id
        )
    except Exception as e:
        print(f"[Article_Pipeline_bg] Background task failed: {e}")

class ArticleResponse(BaseModel):
    id: str
    telegram_sent: bool

@router.post("/generate", response_model=ArticleResponse)
async def generate_article(
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
    author: str = Form(...),
    language: str = Form("uz"),
    db: Client = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    price = 10000 # Default price for article generation
    if user.get("balance", 0.0) < price:
        raise HTTPException(status_code=402, detail="Balansingiz yetarli emas.")

    pipeline = ArticlePipeline()

    new_balance = user.get("balance", 0.0) - price
    try:
        await asyncio.to_thread(
            db.table("users").update({"balance": new_balance}).eq("telegram_id", user["telegram_id"]).execute
        )
    except Exception as e:
        print(f"[API] Balansni yechishda xato: {e}")
        raise HTTPException(status_code=500, detail="Balansni yangilashda xato yuz berdi.")

    if user.get("telegram_id"):
        await send_status_message(
            user["telegram_id"],
            "⏳ Ilmiy maqola yaratish jarayoni boshlandi. Barcha 6-zanjir (Chain) ketma-ketlikda ishlamoqda. Tayyor bo'lgach yuboriladi!"
        )

    # Queue the long-running task
    background_tasks.add_task(
        run_article_pipeline_background,
        pipeline,
        topic,
        author,
        language,
        user.get("telegram_id")
    )

    return ArticleResponse(
        id=str(uuid.uuid4())[:12],
        telegram_sent=True
    )
