import httpx
import os
import re
import html
from app.core.config import settings

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

async def send_obyektivka_to_telegram(
    telegram_id: int,
    full_name: str,
    docx_path: str,
    price: float = 10000.0,
    new_balance: float | None = None,
) -> bool:
    """Send generated obyektivka .docx document to user via Telegram bot."""
    if not settings.TELEGRAM_BOT_TOKEN or not telegram_id:
        return False

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Send text notification
        try:
            safe_name = html.escape(full_name)
            balance_info = ""
            if new_balance is not None:
                balance_info = f"\n\n💰 <b>Xizmat narxi:</b> {int(price):,} so'm\n💳 <b>Qoldiq balansingiz:</b> {int(new_balance):,} so'm"

            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": f"✅ <b>Ma'lumotnoma (Obyektivka) tayyor!</b>\n\n👤 <b>F.I.SH:</b> {safe_name}{balance_info}\n\n📁 Quyida tayyorlangan rasmiy Word (.docx) hujjati ilova qilindi.",
                    "parse_mode": "HTML",
                },
            )
        except Exception as e:
            print(f"[Telegram] Error sending obyektivka message: {e}")

        # 2. Send .docx document
        if docx_path and os.path.exists(docx_path):
            try:
                safe_filename_name = re.sub(r'[^a-zA-Z0-9_\-\u0400-\u04FF\u0510-\u0513 ]', '', full_name)
                clean_name = safe_filename_name.strip().replace(' ', '_') or "Obyektivka"
                file_name = f"{clean_name}_malumotnoma.docx"

                with open(docx_path, "rb") as f:
                    res_doc = await client.post(
                        f"{TELEGRAM_API}/sendDocument",
                        data={
                            "chat_id": str(telegram_id),
                            "caption": f"📄 Ma'lumotnoma (Obyektivka) - {full_name}",
                        },
                        files={
                            "document": (
                                file_name,
                                f,
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                        },
                    )
                    res_doc.raise_for_status()
                return True
            except Exception as e:
                text = getattr(e, 'response', None)
                text = text.text if text else ''
                print(f"[Telegram] Error sending obyektivka document: {e}. {text}")
                return False

    return False
