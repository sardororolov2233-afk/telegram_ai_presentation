from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.api.v1.deps import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["Users"])


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    balance: float
    role: str
    is_premium: bool
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserResponse)
async def get_my_profile(user: User = Depends(get_current_user)):
    """Joriy foydalanuvchi profilini qaytaradi."""
    return UserResponse(
        id=user.telegram_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        balance=float(user.balance),
        role=user.role,
        is_premium=user.is_premium,
        is_active=user.is_active,
    )


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Foydalanuvchi profilini yangilaydi."""
    if body.first_name is not None:
        user.first_name = body.first_name
    if body.last_name is not None:
        user.last_name = body.last_name
    if body.language_code is not None:
        user.language_code = body.language_code
    return UserResponse(
        id=user.telegram_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        balance=float(user.balance),
        role=user.role,
        is_premium=user.is_premium,
        is_active=user.is_active,
    )


# ── Admin endpoints ──────────────────────────────────────────

@router.get("/", tags=["Admin"])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Barcha foydalanuvchilar ro'yxati (faqat admin)."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return [
        {
            "id": u.telegram_id,
            "username": u.username,
            "first_name": u.first_name,
            "balance": float(u.balance),
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.patch("/{telegram_id}/role", tags=["Admin"])
async def change_user_role(
    telegram_id: int,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Foydalanuvchi rolini o'zgartiradi (faqat admin)."""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foydalanuvchi topilmadi")
    user.role = role
    return {"message": f"Rol {role} ga o'zgartirildi"}
