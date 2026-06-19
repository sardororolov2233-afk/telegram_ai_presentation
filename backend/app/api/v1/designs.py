"""
Design Generation API — Grafik dizayn yaratish endpointi.

Pipeline:
  1. Balans tekshirish va yechish (2000 so'm)
  2. Groq (Llama 3) → Prompt optimallashtirish (BEPUL)
  3. FLUX.2 Klein 4B → 3 ta professional rasm yaratish (~$0.045)
  4. Telegram → Rasmlarni foydalanuvchiga yuborish
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
import httpx

from app.core.database import get_db
from app.routes.deps import get_current_user
from app.core.config import settings
from app.services.design.pipeline import run_design_pipeline
from app.services.design.image_generator import STATIC_DIR

router = APIRouter(prefix="/designs", tags=["Designs"])

DESIGN_PRICE = 2000  # so'm


class DesignRequest(BaseModel):
    description: str
    format: str       # instagram | telegram | story
    style: str        # infographic | photorealistic | 3d | minimalism
    lang: str = "uz"  # uz | kaa | ru | en
    send_to_telegram: bool = True


class DesignResponse(BaseModel):
    id: str
    telegram_sent: bool
    images: List[str]


@router.post("/generate", response_model=DesignResponse)
async def generate_design(
    request: Request,
    body: DesignRequest,
    db: Client = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # ── 1. Validatsiya ──────────────────────────────────────
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Dizayn tavsifi bo'sh bo'lmasligi kerak")
    
    if body.format not in ("instagram", "telegram", "story"):
        raise HTTPException(status_code=400, detail="Noto'g'ri format. Mavjud: instagram, telegram, story")
    
    if body.style not in ("infographic", "photorealistic", "3d", "minimalism"):
        raise HTTPException(status_code=400, detail="Noto'g'ri uslub. Mavjud: infographic, photorealistic, 3d, minimalism")

    if body.lang not in ("uz", "kaa", "ru", "en"):
        raise HTTPException(status_code=400, detail="Noto'g'ri til. Mavjud: uz, kaa, ru, en")

    # ── 2. Balans tekshirish ────────────────────────────────
    balance = user.get("balance", 0.0)
    if balance < DESIGN_PRICE:
        raise HTTPException(status_code=402, detail="Balansingiz yetarli emas.")

    # ── 3. Balansdan yechish ────────────────────────────────
    new_balance = balance - DESIGN_PRICE
    try:
        await asyncio.to_thread(
            db.table("users")
            .update({"balance": new_balance})
            .eq("telegram_id", user["telegram_id"])
            .execute
        )
    except Exception as e:
        print(f"[Designs API] Balansni yechishda xato: {e}")
        raise HTTPException(status_code=500, detail="Balansni yangilashda xato yuz berdi.")

    # ── 4. Pipeline ishga tushirish ─────────────────────────
    try:
        filenames = await run_design_pipeline(
            description=body.description,
            format=body.format,
            style=body.style,
            lang=body.lang,
            variant_count=3,
        )
    except Exception as e:
        print(f"[Designs API] Pipeline xatosi: {e}")
        # Balansni qaytarib berish
        try:
            await asyncio.to_thread(
                db.table("users")
                .update({"balance": balance})
                .eq("telegram_id", user["telegram_id"])
                .execute
            )
            print("[Designs API] ⚠️ Balans qaytarildi (pipeline xatosi tufayli)")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Dizayn yaratishda xatolik yuz berdi. Balans qaytarildi.")

    if not filenames:
        # Hech qanday rasm yaratilmadi — balansni qaytarish
        try:
            await asyncio.to_thread(
                db.table("users")
                .update({"balance": balance})
                .eq("telegram_id", user["telegram_id"])
                .execute
            )
            print("[Designs API] ⚠️ Balans qaytarildi (0 ta rasm)")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Rasm yaratib bo'lmadi. Balans qaytarildi.")

    # ── 5. Telegram'ga yuborish ─────────────────────────────
    telegram_sent = False
    if body.send_to_telegram and user.get("telegram_id"):
        try:
            tg_api = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Xabar yuborish
                await client.post(
                    f"{tg_api}/sendMessage",
                    json={
                        "chat_id": user["telegram_id"],
                        "text": "🎨 <b>Dizayningiz tayyor!</b>\n\n"
                                f"📝 Tavsif: {body.description[:100]}...\n"
                                f"📐 Format: {body.format}\n"
                                f"🎭 Uslub: {body.style}\n\n"
                                f"📸 {len(filenames)} ta variant yaratildi:",
                        "parse_mode": "HTML",
                    },
                )
                
                # Rasmlarni yuborish (media group sifatida)
                if len(filenames) > 1:
                    media = []
                    files = {}
                    for i, fname in enumerate(filenames):
                        fpath = os.path.join(STATIC_DIR, fname)
                        if os.path.exists(fpath):
                            attach_name = f"photo{i}"
                            media.append({
                                "type": "photo",
                                "media": f"attach://{attach_name}",
                                "caption": f"Variant #{i + 1}" if i == 0 else "",
                            })
                            files[attach_name] = (fname, open(fpath, "rb"), "image/png")
                    
                    if media:
                        import json
                        await client.post(
                            f"{tg_api}/sendMediaGroup",
                            data={
                                "chat_id": str(user["telegram_id"]),
                                "media": json.dumps(media),
                            },
                            files=files,
                        )
                        
                        # Ochiq fayllarni yopish
                        for attach_name in files:
                            try:
                                files[attach_name][1].close()
                            except Exception:
                                pass
                else:
                    # Bitta rasm bo'lsa oddiy sendPhoto
                    fpath = os.path.join(STATIC_DIR, filenames[0])
                    if os.path.exists(fpath):
                        with open(fpath, "rb") as f:
                            await client.post(
                                f"{tg_api}/sendPhoto",
                                data={"chat_id": str(user["telegram_id"])},
                                files={"photo": (filenames[0], f, "image/png")},
                            )
            
            telegram_sent = True
            print(f"[Designs API] ✅ {len(filenames)} ta rasm Telegram'ga yuborildi")
        except Exception as tg_err:
            print(f"[Designs API] ❌ Telegram yuborish xatosi: {tg_err}")

    # ── 6. Rasmlarni base64 data URL ga aylantirish ───────────
    import base64
    image_data_urls = []
    for fname in filenames:
        fpath = os.path.join(STATIC_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    raw_bytes = f.read()
                
                # MIME type aniqlash
                if raw_bytes[:4] == b'\x89PNG':
                    mime = "image/png"
                elif raw_bytes[:2] == b'\xff\xd8':
                    mime = "image/jpeg"
                else:
                    mime = "image/png"
                
                b64 = base64.b64encode(raw_bytes).decode("utf-8")
                data_url = f"data:{mime};base64,{b64}"
                image_data_urls.append(data_url)
                print(f"[Designs API] 📦 {fname} → base64 ({len(raw_bytes) // 1024} KB)")
            except Exception as e:
                print(f"[Designs API] ❌ Base64 xatosi ({fname}): {e}")
            finally:
                # Faylni o'chirish (endi kerak emas)
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    return DesignResponse(
        id=str(uuid.uuid4())[:12],
        telegram_sent=telegram_sent,
        images=image_data_urls,
    )
