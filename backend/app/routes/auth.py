from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
import asyncio

from app.core.database import get_db
from app.models.user import User
from app.utils.telegram_auth import validate_telegram_init_data, create_access_token
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class TelegramAuthRequest(BaseModel):
    init_data: str  # Telegram WebApp.initData

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(body: TelegramAuthRequest, db: Client = Depends(get_db)):
    """
    Telegram initData orqali autentifikatsiya.
    Frontend: const initData = window.Telegram.WebApp.initData
    """
    user_data = validate_telegram_init_data(body.init_data)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Noto'g'ri yoki eskirgan Telegram ma'lumotlari",
        )

    telegram_id = user_data["id"]

    # Foydalanuvchini topish yoki yaratish
    resp = await asyncio.to_thread(db.table("users").select("*").eq("telegram_id", telegram_id).execute)
    
    if not resp.data:
        new_user = {
            "telegram_id": telegram_id,
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name"),
            "username": user_data.get("username"),
            "language_code": user_data.get("language_code", "uz"),
            "is_premium": user_data.get("is_premium", False),
            "balance": 0.0,
            "role": "user",
            "is_active": True
        }
        res_insert = await asyncio.to_thread(db.table("users").insert(new_user).execute)
        db_user = res_insert.data[0]
    else:
        db_user = resp.data[0]
        # Ma'lumotlarni yangilash
        update_data = {
            "first_name": user_data.get("first_name", db_user.get("first_name")),
            "last_name": user_data.get("last_name", db_user.get("last_name")),
            "username": user_data.get("username", db_user.get("username")),
            "is_premium": user_data.get("is_premium", False),
        }
        res_update = await asyncio.to_thread(db.table("users").update(update_data).eq("telegram_id", telegram_id).execute)
        db_user = res_update.data[0]

    token = create_access_token(telegram_id)

    return AuthResponse(
        access_token=token,
        user={
            "id": db_user["telegram_id"],
            "first_name": db_user.get("first_name", ""),
            "last_name": db_user.get("last_name"),
            "username": db_user.get("username"),
            "balance": float(db_user.get("balance", 0.0)),
            "role": db_user.get("role", "user"),
            "is_premium": db_user.get("is_premium", False),
        },
    )
