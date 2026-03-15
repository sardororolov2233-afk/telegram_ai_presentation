from fastapi import APIRouter, Request, Depends, HTTPException
from supabase import Client
import httpx
import asyncio

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/bot", tags=["Bot"])

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def send_message(chat_id: int, text: str, reply_markup: dict = None):
    """Telegram orqali xabar yuboradi."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)


async def send_mini_app_button(chat_id: int, text: str, button_text: str, web_app_url: str):
    """Mini App tugmasi bilan xabar yuboradi."""
    await send_message(
        chat_id=chat_id,
        text=text,
        reply_markup={
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "web_app": {"url": web_app_url}
                }
            ]]
        }
    )


@router.post("/webhook")
async def bot_webhook(request: Request, db: Client = Depends(get_db)):
    """Telegram bot webhookini qabul qiladi."""
    data = await request.json()

    message = data.get("message", {})

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})

        if text == "/start":
            mini_app_url = settings.FRONTEND_URL or "https://orzu-two.vercel.app"

            await send_mini_app_button(
                chat_id=chat_id,
                text=f"Salom, <b>{user.get('first_name', 'Foydalanuvchi')}</b>! 👋\n\nIlovamizga xush kelibsiz!",
                button_text="🚀 Ilovani ochish",
                web_app_url=mini_app_url,
            )

        elif text == "/balance":
            resp = await asyncio.to_thread(
                db.table("users").select("balance").eq("telegram_id", user["id"]).execute
            )
            balance = float(resp.data[0]["balance"]) if resp.data else 0.0
            await send_message(chat_id, f"💰 Balansingiz: <b>{balance:,.0f} so'm</b>")

    return {"ok": True}


@router.post("/set-webhook")
async def set_webhook():
    """Telegram webhookini o'rnatadi (bir marta ishlatiladi)."""
    if not settings.TELEGRAM_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="TELEGRAM_WEBHOOK_URL sozlanmagan")

    webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/api/v1/bot/webhook"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
        )
    return resp.json()
