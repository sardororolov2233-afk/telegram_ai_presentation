"""A separate publication offer, sent only after article delivery succeeds."""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

PUBLICATION_OFFER_TEXT = (
    '📄 Maqolangiz tayyor! Lekin domlalar va dekanat shunchaki Word faylni qabul qilmaydi — '
    'ularga <b>Rasmiy Jurnalda chop etilganlik haqida SERTIFIKAT</b> kerak. '
    'Shu maqolangizni 24 soat ichida rasmiy "Tamaddun" (Google Scholar) bazasida chop etib, '
    'tayyor sertifikat qilib beraylikmi? Chegirmada atigi 80 ming so\'m. '
    'Hoziroq @tammaddunuz ga yozing!'
)


async def send_publication_offer(telegram_id: int) -> bool:
    if not telegram_id or not settings.TELEGRAM_BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage',
                json={'chat_id': telegram_id, 'text': PUBLICATION_OFFER_TEXT, 'parse_mode': 'HTML'},
            )
            response.raise_for_status()
            return response.json().get('ok') is True
    except Exception:
        # A marketing message cannot undo a completed delivery. Never log a
        # Telegram exception URL: it contains the bot credential.
        logger.warning('Article publication offer could not be delivered')
        return False
