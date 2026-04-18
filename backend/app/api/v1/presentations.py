from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import aiofiles

from app.core.database import get_db
from app.routes.deps import get_current_user
from app.services.presentation.pipeline import PresentationPipeline
from app.services.presentation.telegram_sender import send_status_message

router = APIRouter(prefix="/presentations", tags=["Presentations"])

async def run_pipeline_background(
    pipeline: PresentationPipeline,
    topic: str,
    language: str,
    slide_count: int,
    style: str,
    extra_context: Optional[str],
    design_template: int,
    telegram_id: Optional[int],
    user_image_paths: list,
):
    try:
        await pipeline.run(
            topic=topic,
            language=language,
            slide_count=slide_count,
            style=style,
            extra_context=extra_context,
            design_template=design_template,
            telegram_id=telegram_id,
            user_images=user_image_paths,
        )
    except Exception as e:
        print(f"[Pipeline_bg] Background task failed: {e}")


class PresentationResponse(BaseModel):
    id: str
    telegram_sent: bool
    slide_count: int

@router.post("/generate", response_model=PresentationResponse)
async def generate_presentation(
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
    language: str = Form("uz"),
    slide_count: int = Form(8),
    style: str = Form("professional"),
    extra_context: Optional[str] = Form(None),
    design_template: int = Form(1),
    send_to_telegram: bool = Form(True),
    is_pro: bool = Form(False),
    document_format: str = Form("ppt"),
    images: List[UploadFile] = File(default=[]),
    db: Client = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if slide_count < 3 or slide_count > 20:
        raise HTTPException(status_code=400, detail="Slaydlar soni 3-20 oralig'ida bo'lishi kerak")

    price = slide_count * (500 if is_pro else 300)
    if user.get("balance", 0.0) < price:
        raise HTTPException(status_code=402, detail="Balansingiz yetarli emas.")
        raise HTTPException(status_code=402, detail="Balansingiz yetarli emas.")

    user_image_paths = []
    if images:
        out_dir = "/tmp/user_images"
        os.makedirs(out_dir, exist_ok=True)
        for img in images:
            if img.filename:
                ext = img.filename.split(".")[-1] if "." in img.filename else "jpg"
                tmp_path = os.path.join(out_dir, f"usr_img_{uuid.uuid4().hex}.{ext}")
                try:
                    async with aiofiles.open(tmp_path, 'wb') as out_file:
                        content = await img.read()
                        await out_file.write(content)
                    user_image_paths.append(tmp_path)
                except Exception as e:
                    print(f"[API] Rasm saqlash xatosi: {e}")

    pipeline = PresentationPipeline()

    new_balance = user.get("balance", 0.0) - price
    try:
        await asyncio.to_thread(
            db.table("users").update({"balance": new_balance}).eq("telegram_id", user["telegram_id"]).execute
        )
    except Exception as e:
        print(f"[API] Balansni yechishda xato: {e}")
        raise HTTPException(status_code=500, detail="Balansni yangilashda xato yuz berdi.")

    if send_to_telegram and user.get("telegram_id"):
        await send_status_message(user["telegram_id"], "Fayl yaratilmoqda tayyor bo'lgach sizga taqdim etiladi")

    # Queue the long-running task
    background_tasks.add_task(
        run_pipeline_background,
        pipeline,
        topic,
        language,
        slide_count,
        style,
        extra_context,
        design_template,
        user.get("telegram_id") if send_to_telegram else None,
        user_image_paths,
    )

    return PresentationResponse(
        id=str(uuid.uuid4())[:12],
        telegram_sent=True,
        slide_count=slide_count
    )
