from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.routes.deps import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["Users"])

class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    balance: float
    role: str
    is_premium: bool
    is_active: bool

@router.get("/me", response_model=UserResponse)
async def get_my_profile(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["telegram_id"],
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        language_code=user.get("language_code"),
        balance=float(user.get("balance", 0.0)),
        role=user.get("role", "user"),
        is_premium=user.get("is_premium", False),
        is_active=user.get("is_active", True),
    )

@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UserUpdateRequest,
    db: Client = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    update_data = {}
    if body.first_name is not None:
        update_data["first_name"] = body.first_name
    if body.last_name is not None:
        update_data["last_name"] = body.last_name
    if body.language_code is not None:
        update_data["language_code"] = body.language_code

    if update_data:
        resp = await asyncio.to_thread(
            db.table("users")
            .update(update_data)
            .eq("telegram_id", user["telegram_id"])
            .execute
        )
        user = resp.data[0]

    return UserResponse(
        id=user["telegram_id"],
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        language_code=user.get("language_code"),
        balance=float(user.get("balance", 0.0)),
        role=user.get("role", "user"),
        is_premium=user.get("is_premium", False),
        is_active=user.get("is_active", True),
    )

@router.get("/", tags=["Admin"])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Client = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    resp = await asyncio.to_thread(
        db.table("users").select("*").range(skip, skip + limit - 1).execute
    )
    users = resp.data if resp.data else []
    return [
        {
            "id": u.get("telegram_id"),
            "username": u.get("username"),
            "first_name": u.get("first_name"),
            "balance": float(u.get("balance", 0.0)),
            "role": u.get("role"),
            "is_active": u.get("is_active"),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]

@router.patch("/{telegram_id}/role", tags=["Admin"])
async def change_user_role(
    telegram_id: int,
    role: str,
    db: Client = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    resp = await asyncio.to_thread(
        db.table("users").select("id").eq("telegram_id", telegram_id).execute
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    await asyncio.to_thread(
        db.table("users").update({"role": role}).eq("telegram_id", telegram_id).execute
    )
    return {"message": f"Rol {role} ga o'zgartirildi"}
