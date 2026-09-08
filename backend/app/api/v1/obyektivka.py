from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from supabase import Client
import asyncio
import json
import os

from app.core.database import get_db
from app.routes.deps import get_current_user
from app.services.obyektivka.service import ObyektivkaService
from app.services.obyektivka.telegram_sender import send_obyektivka_to_telegram

router = APIRouter(prefix="/obyektivka", tags=["Obyektivka"])

OBYEKTIVKA_PRICE = 10000.0  # 10 ming so'm

class ObyektivkaApiResponse(BaseModel):
    id: str
    telegram_sent: bool
    docx_url: str
    file_url: str
    message: str
    balance: Optional[float] = None
    price: float = OBYEKTIVKA_PRICE

async def _send_telegram_background(
    telegram_id: int, 
    full_name: str, 
    file_path: str,
    price: float = OBYEKTIVKA_PRICE,
    new_balance: Optional[float] = None,
):
    try:
        await send_obyektivka_to_telegram(
            telegram_id=telegram_id,
            full_name=full_name,
            docx_path=file_path,
            price=price,
            new_balance=new_balance,
        )
    except Exception as e:
        print(f"[ObyektivkaAPI] Telegram background task failed: {e}")

@router.post("/generate", response_model=ObyektivkaApiResponse)
async def generate_obyektivka(
    background_tasks: BackgroundTasks,
    full_name: str = Form(""),
    current_position: str = Form(""),
    birth_date: str = Form(""),
    birth_place: str = Form(""),
    living_address: str = Form(""),
    nationality: str = Form("O'zbek"),
    party: str = Form("Partiyasiz"),
    education_level: str = Form("Oliy"),
    university: str = Form(""),
    education_form: str = Form("kunduzgi"),
    specialty: str = Form(""),
    academic_degree: str = Form("Yo'q"),
    academic_title: str = Form("Yo'q"),
    qualification_level: str = Form("Yo'q"),
    phone: str = Form(""),
    email: str = Form(""),
    languages: str = Form("[]"),
    awards: str = Form("Yo'q"),
    deputy: str = Form("Yo'q"),
    work_history: str = Form("[]"),
    relatives: str = Form("[]"),
    data: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Client = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # ── 1. Balans tekshirish ──────────────────────────────────────
    balance = float(user.get("balance", 0.0) or 0.0)
    if balance < OBYEKTIVKA_PRICE:
        raise HTTPException(
            status_code=402,
            detail="Balansingiz yetarli emas. Obyektivka tayyorlash narxi 10,000 so'm."
        )

    # ── 2. Balansdan 10,000 so'm yechish ─────────────────────────
    new_balance = balance - OBYEKTIVKA_PRICE
    try:
        await asyncio.to_thread(
            db.table("users")
            .update({"balance": new_balance})
            .eq("telegram_id", user["telegram_id"])
            .execute
        )
    except Exception as e:
        print(f"[ObyektivkaAPI] Balansni yechishda xato: {e}")
        raise HTTPException(status_code=500, detail="Balansni yangilashda xato yuz berdi.")

    # Parse bundle fallback if available
    bundle = {}
    if data:
        try:
            bundle = json.loads(data)
        except Exception:
            bundle = {}

    fn = full_name or bundle.get("fullName", "")
    if not fn.strip():
        # Balansni qaytarib berish
        await asyncio.to_thread(
            db.table("users").update({"balance": balance}).eq("telegram_id", user["telegram_id"]).execute
        )
        raise HTTPException(status_code=400, detail="F.I.SH. kiritilishi shart")

    cp = current_position or bundle.get("currentPosition", "")
    bd = birth_date or bundle.get("birthDate", "")
    bp = birth_place or bundle.get("birthPlace", "")
    la = living_address or bundle.get("livingAddress", "")
    nat = nationality or bundle.get("nationality", "O'zbek")
    pty = party or bundle.get("party", "Partiyasiz")
    el = education_level or bundle.get("educationLevel", "Oliy")
    uni = university or bundle.get("university", "")
    ef = education_form or bundle.get("educationForm", "kunduzgi")
    spec = specialty or bundle.get("specialty", "")
    ad = academic_degree or bundle.get("academicDegree", "Yo'q")
    at = academic_title or bundle.get("academicTitle", "Yo'q")
    ql = qualification_level or bundle.get("qualificationLevel", "Yo'q")
    ph = phone or bundle.get("phone", "")
    em = email or bundle.get("email", "")
    aw = awards or bundle.get("awards", "Yo'q")
    dep = deputy or bundle.get("deputy", "Yo'q")

    # Parse languages
    langs_list: List[str] = []
    if languages:
        try:
            parsed = json.loads(languages)
            if isinstance(parsed, list):
                langs_list = [str(x) for x in parsed]
        except Exception:
            langs_list = [l.strip() for l in languages.split(",") if l.strip()]
    if not langs_list and "languages" in bundle:
        langs_list = bundle.get("languages") or []

    # Parse work history
    work_list: List[Dict[str, Any]] = []
    if work_history:
        try:
            parsed_w = json.loads(work_history)
            if isinstance(parsed_w, list):
                work_list = parsed_w
        except Exception:
            pass
    if not work_list and "workHistory" in bundle:
        work_list = bundle.get("workHistory") or []

    # Parse relatives
    relatives_list: List[Dict[str, Any]] = []
    if relatives:
        try:
            parsed_r = json.loads(relatives)
            if isinstance(parsed_r, list):
                relatives_list = parsed_r
        except Exception:
            pass
    if not relatives_list and "relatives" in bundle:
        relatives_list = bundle.get("relatives") or []

    # Read photo bytes if uploaded
    photo_bytes: Optional[bytes] = None
    if photo and photo.filename:
        try:
            photo_bytes = await photo.read()
        except Exception as e:
            print(f"[ObyektivkaAPI] Error reading photo upload: {e}")

    # ── 3. Hujjat generatsiyasi ──────────────────────────────────
    try:
        service = ObyektivkaService()
        result = service.generate(
            full_name=fn,
            current_position=cp,
            birth_date=bd,
            birth_place=bp,
            living_address=la,
            nationality=nat,
            party=pty,
            education_level=el,
            university=uni,
            education_form=ef,
            specialty=spec,
            academic_degree=ad,
            academic_title=at,
            qualification_level=ql,
            phone=ph,
            email=em,
            languages=langs_list,
            awards=aw,
            deputy=dep,
            work_history=work_list,
            relatives=relatives_list,
            photo_bytes=photo_bytes,
        )
    except Exception as e:
        print(f"[ObyektivkaAPI] Generation error: {e}")
        # Balansni qaytarish (Rollback)
        try:
            await asyncio.to_thread(
                db.table("users").update({"balance": balance}).eq("telegram_id", user["telegram_id"]).execute
            )
        except Exception as rb_err:
            print(f"[ObyektivkaAPI] Rollback error: {rb_err}")
        raise HTTPException(status_code=500, detail=f"Obyektivka yaratishda xatolik yuz berdi: {str(e)}")

    # ── 4. Telegram bot orqali jo'natish ─────────────────────────
    telegram_id = user.get("telegram_id")
    telegram_sent = False
    if telegram_id:
        background_tasks.add_task(
            _send_telegram_background,
            telegram_id=telegram_id,
            full_name=fn,
            file_path=result["file_path"],
            price=OBYEKTIVKA_PRICE,
            new_balance=new_balance,
        )
        telegram_sent = True

    return ObyektivkaApiResponse(
        id=result["id"],
        telegram_sent=telegram_sent,
        docx_url=result["docx_url"],
        file_url=result["file_url"],
        message="Obyektivka muvaffaqiyatli tayyorlandi! Hisobingizdan 10,000 so'm yechildi.",
        balance=new_balance,
        price=OBYEKTIVKA_PRICE
    )
