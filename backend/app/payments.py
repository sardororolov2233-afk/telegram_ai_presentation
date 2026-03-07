from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from decimal import Decimal

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
    redirect_url: str | None = None


@router.post("/create", response_model=PaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """To'lov yaratadi va to'lov sahifasiga URL qaytaradi."""
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
    """Payme webhook - to'lov tasdiqlanganda chaqiriladi."""
    data = await request.json()
    method = data.get("method")
    params = data.get("params", {})

    # Payme JSON-RPC protokoli
    if method == "PerformTransaction":
        transaction_id = params.get("id")
        result = await db.execute(
            select(Payment).where(Payment.external_id == str(transaction_id))
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = PaymentStatus.COMPLETED
            # Balansni to'ldirish
            result2 = await db.execute(select(User).where(User.id == payment.user_id))
            user = result2.scalar_one_or_none()
            if user:
                user.balance = float(user.balance) + float(payment.amount)

        return {"result": {"transaction": transaction_id, "perform_time": 0, "state": 2}}

    return {"result": {}}


@router.post("/click/callback")
async def click_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Click webhook - to'lov tasdiqlanganda chaqiriladi."""
    data = await request.json()
    payment_id = data.get("merchant_trans_id")

    result = await db.execute(select(Payment).where(Payment.id == int(payment_id)))
    payment = result.scalar_one_or_none()

    if payment and data.get("error") == 0:
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


# === Helper functions ===

def _generate_payme_url(payment: Payment) -> str:
    from app.core.config import settings
    import base64

    merchant_id = settings.PAYME_MERCHANT_ID or "YOUR_MERCHANT_ID"
    amount_tiyin = int(payment.amount * 100)  # so'mdan tiyinga
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
