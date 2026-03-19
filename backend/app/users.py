from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.payment import Payment, PaymentStatus
from app.api.v1.deps import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Joriy foydalanuvchi ma'lumotlari."""
    return {
        "id": user.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "balance": float(user.balance),
        "role": user.role,
        "is_premium": user.is_premium,
        "created_at": user.created_at,
    }


@router.get("/admin/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: umumiy statistika."""
    total_users = await db.scalar(select(func.count(User.id)))
    total_payments = await db.scalar(
        select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.COMPLETED)
    )
    active_today = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )

    return {
        "total_users": total_users or 0,
        "total_revenue": float(total_payments or 0),
        "active_users": active_today or 0,
    }


@router.get("/admin/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: barcha foydalanuvchilar ro'yxati."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.telegram_id,
            "name": f"{u.first_name} {u.last_name or ''}".strip(),
            "username": u.username,
            "balance": float(u.balance),
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]
