"""
Telegram Sender
===============
Tayyor PPTX va PDF fayllarni Telegram botga yuboradi.
Foydalanuvchiga bevosita fayl va mini-app tugmasi jo'natadi.
"""

import httpx
import os
from app.core.config import settings

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def send_presentation_to_telegram(
    telegram_id: int,
    topic: str,
    pptx_path: str,
    pdf_path: str,
    slide_count: int,
    preview_url: str | None = None,
) -> bool:
    """
    Foydalanuvchiga:
    1. Xabar + preview tugmasi
    2. PPTX fayl
    3. PDF fayl
    Yuboradi.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Kirish xabari + preview tugmasi
        intro_text = (
            f"🎯 <b>Taqdimotingiz tayyor!</b>\n\n"
            f"📌 Mavzu: <i>{topic}</i>\n"
            f"📊 Slaydlar soni: <b>{slide_count}</b>\n\n"
            f"Quyidagi fayllarni yuklang 👇"
        )

        keyboard = None
        if preview_url:
            keyboard = {
                "inline_keyboard": [[
                    {"text": "🌐 HTML ko'rinish", "web_app": {"url": preview_url}}
                ]]
            }

        msg_payload = {
            "chat_id": telegram_id,
            "text": intro_text,
            "parse_mode": "HTML",
        }
        if keyboard:
            msg_payload["reply_markup"] = keyboard

        await client.post(f"{TELEGRAM_API}/sendMessage", json=msg_payload)

        # 2. PPTX fayl
        if os.path.exists(pptx_path):
            with open(pptx_path, "rb") as f:
                await client.post(
                    f"{TELEGRAM_API}/sendDocument",
                    data={
                        "chat_id": str(telegram_id),
                        "caption": "📊 PowerPoint taqdimot (.pptx)",
                        "parse_mode": "HTML",
                    },
                    files={"document": (f"{topic[:40]}.pptx", f,
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                )

        # 3. PDF fayl
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await client.post(
                    f"{TELEGRAM_API}/sendDocument",
                    data={
                        "chat_id": str(telegram_id),
                        "caption": "📄 PDF taqdimot (.pdf)",
                        "parse_mode": "HTML",
                    },
                    files={"document": (f"{topic[:40]}.pdf", f, "application/pdf")},
                )

        # 4. Yakuniy xabar
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": telegram_id,
                "text": "✅ Hammasi yuborildi! Yaxshi taqdimot o'ting 🎉",
                "parse_mode": "HTML",
            },
        )

    return True
