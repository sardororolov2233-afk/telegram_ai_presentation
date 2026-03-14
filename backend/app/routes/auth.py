from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
async def telegram_auth(body: TelegramAuthRequest, db: AsyncSession = Depends(get_db)):
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
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=telegram_id,
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name"),
            username=user_data.get("username"),
            language_code=user_data.get("language_code", "uz"),
            is_premium=user_data.get("is_premium", False),
        )
        db.add(user)
        await db.flush()
    else:
        # Ma'lumotlarni yangilash
        user.first_name = user_data.get("first_name", user.first_name)
        user.last_name = user_data.get("last_name", user.last_name)
        user.username = user_data.get("username", user.username)
        user.is_premium = user_data.get("is_premium", False)

    token = create_access_token(user.telegram_id)

    return AuthResponse(
        access_token=token,
        user={
            "id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "balance": float(user.balance),
            "role": user.role,
            "is_premium": user.is_premium,
        },
    )
