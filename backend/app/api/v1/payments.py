from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
import base64
import hashlib
import hmac

from app.core.database import get_db
from app.models.user import User
from app.models.payment import Payment, PaymentStatus, PaymentProvider
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/payments", tags=["Payments"])


class CreatePaymentRequest(BaseModel):
    amount: float
    provider: PaymentProvider
    description: str = ""


class PaymentResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: PaymentStatus
    provider: PaymentProvider
    redirect_url: Optional[str] = None


@router.post("/create", response_model=PaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """To'lov yaratadi va to'lov sahifasiga URL qaytaradi."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Summa 0 dan katta bo'lishi kerak")

    payment = Payment(
        user_id=user.id,
        amount=body.amount,
        currency="UZS",
        provider=body.provider,
        description=body.description,
    )
    db.add(payment)
    await db.flush()

    redirect_url = None
    if body.provider == PaymentProvider.PAYME:
        redirect_url = _generate_payme_url(payment)
    elif body.provider == PaymentProvider.CLICK:
        redirect_url = _generate_click_url(payment)

    return PaymentResponse(
        id=payment.id,
        amount=float(payment.amount),
        currency=payment.currency,
        status=payment.status,
        provider=payment.provider,
        redirect_url=redirect_url,
    )


@router.post("/payme/callback")
async def payme_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Payme webhook — to'lov tasdiqlanganda chaqiriladi."""
    from app.core.config import settings

    # ✅ Payme Basic Auth tekshiruvi
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            _, password = decoded.split(":", 1)
            if password != settings.PAYME_SECRET_KEY:
                return {"error": {"code": -32504, "message": "Insufficient privilege"}}
        except Exception:
            return {"error": {"code": -32504, "message": "Insufficient privilege"}}
    elif settings.PAYME_SECRET_KEY:
        # Secret key sozlangan bo'lsa, autentifikatsiya majburiy
        return {"error": {"code": -32504, "message": "Insufficient privilege"}}

    data = await request.json()
    method = data.get("method")
    params = data.get("params", {})

    if method == "PerformTransaction":
        transaction_id = params.get("id")
        result = await db.execute(
            select(Payment).where(Payment.external_id == str(transaction_id))
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = PaymentStatus.COMPLETED
            result2 = await db.execute(select(User).where(User.id == payment.user_id))
            user = result2.scalar_one_or_none()
            if user:
                user.balance = float(user.balance) + float(payment.amount)

        return {"result": {"transaction": transaction_id, "perform_time": 0, "state": 2}}

    if method == "CreateTransaction":
        order_id = params.get("account", {}).get("order_id")
        amount = params.get("amount", 0) / 100  # tiyin → so'm
        transaction_id = params.get("id")

        result = await db.execute(select(Payment).where(Payment.id == int(order_id)))
        payment = result.scalar_one_or_none()
        if not payment:
            return {"error": {"code": -31050, "message": "Order not found"}}

        payment.external_id = str(transaction_id)
        return {"result": {"create_time": 0, "transaction": transaction_id, "state": 1}}

    return {"result": {}}


@router.post("/click/callback")
async def click_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Click webhook — to'lov tasdiqlanganda chaqiriladi."""
    from app.core.config import settings

    data = await request.json()

    # ✅ Click imzo tekshiruvi
    service_id = data.get("service_id")
    click_trans_id = data.get("click_trans_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")
    amount = data.get("amount", 0)
    action = data.get("action", 0)
    sign_time = data.get("sign_time", "")
    sign_string = data.get("sign_string", "")

    if settings.CLICK_SECRET_KEY:
        expected_sign = hashlib.md5(
            f"{click_trans_id}{service_id}{settings.CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}".encode()
        ).hexdigest()
        if sign_string != expected_sign:
            return {"error": -1, "error_note": "SIGN CHECK FAILED!"}

    try:
        payment_id = int(merchant_trans_id)
    except (ValueError, TypeError):
        return {"error": -5, "error_note": "Invalid merchant_trans_id"}

    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment:
        return {"error": -5, "error_note": "Payment not found"}

    if data.get("error") == 0:
        payment.status = PaymentStatus.COMPLETED
        result2 = await db.execute(select(User).where(User.id == payment.user_id))
        user = result2.scalar_one_or_none()
        if user:
            user.balance = float(user.balance) + float(payment.amount)

    return {"error": 0, "error_note": "Success"}


@router.get("/history")
async def payment_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc()).limit(20)
    )
    payments = result.scalars().all()
    return [
        {
            "id": p.id,
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status,
            "provider": p.provider,
            "description": p.description,
            "created_at": p.created_at,
        }
        for p in payments
    ]


# ── Helper functions ────────────────────────────────────────

def _generate_payme_url(payment: Payment) -> str:
    from app.core.config import settings

    merchant_id = settings.PAYME_MERCHANT_ID or "YOUR_MERCHANT_ID"
    amount_tiyin = int(payment.amount * 100)
    params = f"m={merchant_id};ac.order_id={payment.id};a={amount_tiyin}"
    encoded = base64.b64encode(params.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"


def _generate_click_url(payment: Payment) -> str:
    from app.core.config import settings

    service_id = settings.CLICK_SERVICE_ID or "YOUR_SERVICE_ID"
    amount = int(payment.amount)
    return (
        f"https://my.click.uz/services/pay?"
        f"service_id={service_id}&merchant_id={service_id}"
        f"&amount={amount}&transaction_param={payment.id}&return_url=https://t.me/your_bot"
    )
