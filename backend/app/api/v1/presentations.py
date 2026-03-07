from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import os

from app.core.database import get_db
from app.models.user import User
from app.api.v1.deps import get_current_user
from app.services.presentation.pipeline import PresentationPipeline

router = APIRouter(prefix="/presentations", tags=["Presentations"])


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class SlideContent(BaseModel):
    title: str
    body: str  # Markdown yoki oddiy matn


class PresentationRequest(BaseModel):
    topic: str                          # "Süni intellekt va kelajak"
    language: str = "uz"               # "uz" | "ru" | "en"
    slide_count: int = 8               # Nechta slide
    style: str = "professional"        # "professional" | "creative" | "minimal"
    extra_context: Optional[str] = None  # Qo'shimcha ma'lumotlar
    user_prompt: Optional[str] = None    # Dizayn uslubi, masalan: "antik, jigarrang, klassik"
    send_to_telegram: bool = True       # Botga yuborsinmi


class PresentationResponse(BaseModel):
    id: str
    html_preview: str          # HTML taqdimot (brauzerda ko'rish uchun)
    pptx_url: str              # Yuklab olish uchun
    pdf_url: str               # Yuklab olish uchun
    telegram_sent: bool
    slide_count: int


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/generate", response_model=PresentationResponse)
async def generate_presentation(
    body: PresentationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.slide_count < 3 or body.slide_count > 20:
        raise HTTPException(status_code=400, detail="Slaydlar soni 3-20 oralig'ida bo'lishi kerak")

    pipeline = PresentationPipeline()

    result = await pipeline.run(
        topic=body.topic,
        language=body.language,
        slide_count=body.slide_count,
        style=body.style,
        extra_context=body.extra_context,
        user_prompt=body.user_prompt,
        telegram_id=user.telegram_id if body.send_to_telegram else None,
    )

    return PresentationResponse(**result)


@router.get("/download/{presentation_id}/{file_type}")
async def download_file(presentation_id: str, file_type: str):
    if file_type not in ("pptx", "pdf"):
        raise HTTPException(status_code=400, detail="Fayl turi noto'g'ri")

    # Path traversal dan himoya
    safe_id = presentation_id.replace("..", "").replace("/", "").replace("\\", "")
    if not safe_id:
        raise HTTPException(status_code=400, detail="Noto'g'ri fayl ID")

    # Pipeline bilan bir xil papka (cross-platform)
    output_dir = os.path.join(os.path.expanduser("~"), "presentations_cache")
    file_path = os.path.join(output_dir, f"{safe_id}.{file_type}")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fayl topilmadi yoki muddati tugagan")

    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if file_type == "pptx" else "application/pdf"
    )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=f"presentation.{file_type}",
    )
