import httpx
import os
import re
import html
from app.core.config import settings

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

async def send_status_message(telegram_id: int, message: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            res.raise_for_status()
            return True
        except Exception as e:
            text = getattr(e, 'response', None)
            text = text.text if text else ''
            print(f"[Telegram] Error sending status message: {e}. {text}")
            return False

async def send_presentation_to_telegram(
    telegram_id: int,
    topic: str,
    pptx_path: str,
    slide_count: int,
) -> bool:
    # Increase timeout since files can take longer to upload
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            safe_html_topic = html.escape(topic)
            res_msg = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": f"Taqdimotingiz tayyor!\n\nMavzu: {safe_html_topic}\nSlaydlar: {slide_count}",
                    "parse_mode": "HTML",
                },
            )
            res_msg.raise_for_status()
        except Exception as e:
            text = getattr(e, 'response', None)
            text = text.text if text else ''
            print(f"[Telegram] Error sending presentation info message: {e}. {text}")

        if pptx_path and os.path.exists(pptx_path):
            try:
                # Sanitize topic for filename to avoid Telegram API breaking on bad characters
                safe_topic = re.sub(r'[^a-zA-Z0-9_\-\u0400-\u04FF\u0510-\u0513 ]', '', topic)
                
                is_pdf = pptx_path.lower().endswith('.pdf')
                ext = 'pdf' if is_pdf else 'pptx'
                mime_type = "application/pdf" if is_pdf else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                caption = "Taqdimot (.pdf)" if is_pdf else "PowerPoint taqdimot (.pptx)"
                
                file_name = f"{safe_topic[:40].strip() or 'Taqdimot'}.{ext}"
                
                with open(pptx_path, "rb") as f:
                    res_doc = await client.post(
                        f"{TELEGRAM_API}/sendDocument",
                        data={
                            "chat_id": str(telegram_id),
                            "caption": caption,
                        },
                        files={"document": (file_name, f, mime_type)},
                    )
                    res_doc.raise_for_status()
            except Exception as e:
                text = getattr(e, 'response', None)
                text = text.text if text else ''
                print(f"[Telegram] Error sending document: {e}. {text}")
                raise  # Re-raise so that calling function knows it failed

    return True

async def send_url_document_to_telegram(
    telegram_id: int,
    topic: str,
    download_url: str,
    slide_count: int,
) -> bool:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            safe_html_topic = html.escape(topic)
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": f"Taqdimotingiz tayyor!\n\nMavzu: {safe_html_topic}\nSlaydlar: {slide_count}",
                    "parse_mode": "HTML",
                },
            )
        except Exception as e:
            print(f"[Telegram] Error sending info message: {e}")

        try:
            res_doc = await client.post(
                f"{TELEGRAM_API}/sendDocument",
                json={
                    "chat_id": telegram_id,
                    "document": download_url,
                    "caption": "Sizning taqdimotingiz tayyor! 📁✨",
                },
            )
            res_doc.raise_for_status()
        except Exception as e:
            text = getattr(e, 'response', None)
            text = text.text if text else ''
            print(f"[Telegram] Error sending URL document: {e}. {text}")
            raise

    return True

