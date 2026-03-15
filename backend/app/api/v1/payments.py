from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client
import asyncio
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
import base64
import hashlib
import hmac
from datetime import datetime

from app.core.database import get_db
from app.models.user import User
from app.models.payment import PaymentStatus, PaymentProvider
from app.routes.deps import get_current_user

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
    db: Client = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """To'lov yaratadi va to'lov sahifasiga URL qaytaradi."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Summa 0 dan katta bo'lishi kerak")

    new_payment = {
        "user_id": user.telegram_id,  # Assume payment uses telegram_id or we need to align IDs
        "amount": body.amount,
        "currency": "UZS",
        "provider": body.provider.value,
        "status": PaymentStatus.PENDING.value,
        "description": body.description,
    }

    # Insert to Supabase payments
    resp = await asyncio.to_thread(db.table("payments").insert(new_payment).execute)
    
    if not resp.data:
        raise HTTPException(status_code=500, detail="To'lov yaratishda xatolik yuz berdi")
        
    payment_data = resp.data[0]
    payment_id = payment_data["id"]

    redirect_url = None
    if body.provider == PaymentProvider.PAYME:
        redirect_url = _generate_payme_url(payment_id, body.amount)
    elif body.provider == PaymentProvider.CLICK:
        redirect_url = _generate_click_url(payment_id, body.amount)

    return PaymentResponse(
        id=payment_id,
        amount=float(payment_data["amount"]),
        currency=payment_data["currency"],
        status=payment_data["status"],
        provider=payment_data["provider"],
        redirect_url=redirect_url,
    )


@router.post("/payme/callback")
async def payme_callback(request: Request, db: Client = Depends(get_db)):
    """Payme webhook — to'lov tasdiqlanganda chaqiriladi."""
    from app.core.config import settings

    # Payme Basic Auth tekshiruvi
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
        return {"error": {"code": -32504, "message": "Insufficient privilege"}}

    data = await request.json()
    method = data.get("method")
    params = data.get("params", {})

    if method == "PerformTransaction":
        transaction_id = params.get("id")
        
        resp = await asyncio.to_thread(db.table("payments").select("*").eq("external_id", str(transaction_id)).execute)
        
        if resp.data:
            payment = resp.data[0]
            if payment["status"] != PaymentStatus.COMPLETED.value:
                # Update status
                await asyncio.to_thread(
                    db.table("payments").update({"status": PaymentStatus.COMPLETED.value}).eq("id", payment["id"]).execute
                )
                
                # Fetch user
                user_resp = await asyncio.to_thread(
                    db.table("users").select("*").eq("telegram_id", payment["user_id"]).execute
                )
                if user_resp.data:
                    user = user_resp.data[0]
                    new_balance = float(user.get("balance", 0)) + float(payment["amount"])
                    await asyncio.to_thread(
                        db.table("users").update({"balance": new_balance}).eq("telegram_id", payment["user_id"]).execute
                    )

        return {"result": {"transaction": transaction_id, "perform_time": 0, "state": 2}}

    if method == "CreateTransaction":
        order_id = params.get("account", {}).get("order_id")
        amount = params.get("amount", 0) / 100  # tiyin → so'm
        transaction_id = params.get("id")

        resp = await asyncio.to_thread(db.table("payments").select("*").eq("id", int(order_id)).execute)
        
        if not resp.data:
            return {"error": {"code": -31050, "message": "Order not found"}}

        await asyncio.to_thread(
            db.table("payments").update({"external_id": str(transaction_id)}).eq("id", int(order_id)).execute
        )
        return {"result": {"create_time": 0, "transaction": transaction_id, "state": 1}}

    return {"result": {}}


@router.post("/click/callback")
async def click_callback(request: Request, db: Client = Depends(get_db)):
    """Click webhook — to'lov tasdiqlanganda chaqiriladi."""
    from app.core.config import settings

    data = await request.headers  # Or form, depending on CLICK docs (Click usually sends POST form-urlencoded)
    # Fast approach for Click
    try:
        form_data = await request.form()
        data = dict(form_data)
    except Exception:
        data = await request.json()

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

    resp = await asyncio.to_thread(db.table("payments").select("*").eq("id", payment_id).execute)

    if not resp.data:
        return {"error": -5, "error_note": "Payment not found"}

    payment = resp.data[0]

    if str(data.get("error", "0")) == "0":
        if payment["status"] != PaymentStatus.COMPLETED.value:
            await asyncio.to_thread(
                db.table("payments").update({"status": PaymentStatus.COMPLETED.value}).eq("id", payment_id).execute
            )
            
            user_resp = await asyncio.to_thread(
                db.table("users").select("*").eq("telegram_id", payment["user_id"]).execute
            )
            if user_resp.data:
                user = user_resp.data[0]
                new_balance = float(user.get("balance", 0)) + float(payment["amount"])
                await asyncio.to_thread(
                    db.table("users").update({"balance": new_balance}).eq("telegram_id", payment["user_id"]).execute
                )

    return {"error": 0, "error_note": "Success"}


@router.get("/history")
async def payment_history(
    db: Client = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resp = await asyncio.to_thread(
        db.table("payments").select("*").eq("user_id", user.telegram_id).order("created_at", desc=True).limit(20).execute
    )
    
    payments = resp.data if resp.data else []
    return [
        {
            "id": p["id"],
            "amount": float(p["amount"]),
            "currency": p.get("currency", "UZS"),
            "status": p["status"],
            "provider": p["provider"],
            "description": p.get("description", ""),
            "created_at": p.get("created_at", ""),
        }
        for p in payments
    ]


# ── Helper functions ────────────────────────────────────────

def _generate_payme_url(payment_id: int, amount: float) -> str:
    from app.core.config import settings
    merchant_id = settings.PAYME_MERCHANT_ID or "YOUR_MERCHANT_ID"
    amount_tiyin = int(amount * 100)
    params = f"m={merchant_id};ac.order_id={payment_id};a={amount_tiyin}"
    encoded = base64.b64encode(params.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"


def _generate_click_url(payment_id: int, amount: float) -> str:
    from app.core.config import settings
    service_id = settings.CLICK_SERVICE_ID or "YOUR_SERVICE_ID"
    return (
        f"https://my.click.uz/services/pay?"
        f"service_id={service_id}&merchant_id={service_id}"
        f"&amount={int(amount)}&transaction_param={payment_id}&return_url=https://t.me/your_bot"
    )
