from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import FileResponse
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import aiofiles

from app.core.database import get_db
from app.models.user import User
from app.routes.deps import get_current_user
from app.services.presentation.pipeline import PresentationPipeline

router = APIRouter(prefix="/presentations", tags=["Presentations"])

class PresentationResponse(BaseModel):
    id: str
    pptx_url: str
    telegram_sent: bool
    slide_count: int

@router.post("/generate", response_model=PresentationResponse)
async def generate_presentation(
    topic: str = Form(...),
    language: str = Form("uz"),
    slide_count: int = Form(8),
    style: str = Form("professional"),
    extra_context: Optional[str] = Form(None),
    design_template: int = Form(1),
    send_to_telegram: bool = Form(True),
    images: List[UploadFile] = File(default=[]),
    db: Client = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if slide_count < 3 or slide_count > 20:
        raise HTTPException(status_code=400, detail="Slaydlar soni 3-20 oralig'ida bo'lishi kerak")

    price = slide_count * 600
    if user.balance < price:
        raise HTTPException(status_code=402, detail="Balansingiz yetarli emas. Iltimos, hisobingizni to'ldiring.")

    user_image_paths = []
    if images:
        out_dir = os.path.join(os.path.expanduser("~"), "presentations_cache")
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

    result = await pipeline.run(
        topic=topic,
        language=language,
        slide_count=slide_count,
        style=style,
        extra_context=extra_context,
        design_template=design_template,
        telegram_id=user.telegram_id if send_to_telegram else None,
        user_images=user_image_paths
    )

    new_balance = user.balance - price
    try:
        await asyncio.to_thread(
            db.table("users").update({"balance": new_balance}).eq("telegram_id", user.telegram_id).execute
        )
    except Exception as e:
        print(f"[API] Balansni yechishda xato: {e}")

    return PresentationResponse(**result)


@router.get("/download/{presentation_id}/{file_type}")
async def download_file(presentation_id: str, file_type: str):
    if file_type != "pptx":
        raise HTTPException(status_code=400, detail="Fayl turi noto'g'ri (faqat pptx qo'llab-quvvatlanadi)")

    safe_id = presentation_id.replace("..", "").replace("/", "").replace("\\", "")
    if not safe_id:
        raise HTTPException(status_code=400, detail="Noto'g'ri fayl ID")

    output_dir = os.path.join(os.path.expanduser("~"), "presentations_cache")
    file_path = os.path.join(output_dir, f"{safe_id}.pptx")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fayl topilmadi yoki muddati tugagan")

    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=f"presentation.pptx",
    )
