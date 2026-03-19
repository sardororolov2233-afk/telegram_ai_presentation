from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
import asyncio

from app.core.database import get_db
from app.utils.telegram_auth import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Client = Depends(get_db),
) -> dict:
    token = credentials.credentials
    telegram_id = decode_access_token(token)

    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token noto'g'ri yoki muddati tugagan",
        )

    resp = await asyncio.to_thread(
        db.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute
    )

    if not resp.data or not resp.data[0].get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi topilmadi",
        )

    return resp.data[0]


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin huquqi talab etiladi",
        )
    return user
