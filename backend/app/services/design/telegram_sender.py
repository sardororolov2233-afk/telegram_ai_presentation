"""Deliver generated designs without treating a Telegram failure as generation failure."""
from contextlib import ExitStack
import json
import logging
from pathlib import Path
from typing import Sequence

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _confirmed(response: httpx.Response, count: int) -> bool:
    if not response.is_success:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict) or payload.get('ok') is not True:
        return False
    result = payload.get('result')
    messages = result if isinstance(result, list) else [result]
    return len(messages) == count and all(
        isinstance(message, dict) and type(message.get('message_id')) is int
        and message['message_id'] > 0 for message in messages
    )


async def send_design_images(telegram_id: int, image_paths: Sequence[Path],
                             description: str, format: str, style: str) -> bool:
    if not telegram_id or not settings.TELEGRAM_BOT_TOKEN or not image_paths:
        return False
    api = 'https://api.telegram.org/bot' + settings.TELEGRAM_BOT_TOKEN
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Plain text keeps user-supplied '<', '&', etc. out of HTML parsing.
            try:
                info = await client.post(api + '/sendMessage', json={
                    'chat_id': telegram_id,
                    'text': '🎨 Dizayningiz tayyor!\n\n'
                            f'📝 Tavsif: {description[:100]}\n'
                            f'📐 Format: {format}\n🎭 Uslub: {style}\n\n'
                            f'📸 {len(image_paths)} ta variant yaratildi:',
                })
                if not _confirmed(info, 1):
                    logger.warning('Design Telegram info delivery was not confirmed')
            except Exception:
                # An informational message must not prevent delivery of the images.
                logger.warning('Design Telegram info delivery failed')

            with ExitStack() as stack:
                files = {}
                media = []
                for index, path in enumerate(image_paths):
                    path = Path(path)
                    attachment = 'photo' if len(image_paths) == 1 else f'photo{index}'
                    files[attachment] = (path.name, stack.enter_context(path.open('rb')), 'image/png')
                    media.append({'type': 'photo', 'media': f'attach://{attachment}',
                                  'caption': f'Variant #{index + 1}'})
                if len(image_paths) == 1:
                    response = await client.post(api + '/sendPhoto',
                        data={'chat_id': str(telegram_id)}, files=files)
                else:
                    response = await client.post(api + '/sendMediaGroup',
                        data={'chat_id': str(telegram_id), 'media': json.dumps(media)}, files=files)
                delivered = _confirmed(response, len(image_paths))
            if not delivered:
                logger.warning('Design Telegram image delivery was not confirmed')
            return delivered
    except Exception:
        # Exception text and request URLs can contain the bot token.
        logger.warning('Design Telegram image delivery failed')
        return False
