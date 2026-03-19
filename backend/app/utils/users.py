from fastapi import APIRouter, Depends
from supabase import Client
import asyncio

from app.core.database import get_db
from app.api.v1.deps import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["telegram_id"],
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name"),
        "username": user.get("username"),
        "balance": float(user.get("balance", 0.0)),
        "role": user.get("role", "user"),
        "is_premium": user.get("is_premium", False),
        "created_at": user.get("created_at"),
    }


@router.get("/admin/stats")
async def admin_stats(
    db: Client = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    users_resp = await asyncio.to_thread(
        db.table("users").select("id", count="exact").execute
    )
    total_users = users_resp.count or 0

    active_resp = await asyncio.to_thread(
        db.table("users").select("id", count="exact").eq("is_active", True).execute
    )
    active_users = active_resp.count or 0

    return {
        "total_users": total_users,
        "total_revenue": 0.0,
        "active_users": active_users,
    }


@router.get("/admin/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    db: Client = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    resp = await asyncio.to_thread(
        db.table("users")
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute
    )
    users = resp.data or []
    return [
        {
            "id": u.get("telegram_id"),
            "name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
            "username": u.get("username"),
            "balance": float(u.get("balance", 0.0)),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]
