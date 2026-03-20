import httpx
import os
from app.core.config import settings

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

async def send_presentation_to_telegram(
    telegram_id: int,
    topic: str,
    pptx_path: str,
    slide_count: int,
) -> bool:
    async with httpx.AsyncClient(timeout=60.0) as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": telegram_id,
                "text": f"Taqdimotingiz tayyor!\n\nMavzu: {topic}\nSlaydlar: {slide_count}",
                "parse_mode": "HTML",
            },
        )

        if pptx_path and os.path.exists(pptx_path):
            with open(pptx_path, "rb") as f:
                await client.post(
                    f"{TELEGRAM_API}/sendDocument",
                    data={
                        "chat_id": str(telegram_id),
                        "caption": "PowerPoint taqdimot (.pptx)",
                    },
                    files={"document": (f"{topic[:40]}.pptx", f,
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                )

    return True
