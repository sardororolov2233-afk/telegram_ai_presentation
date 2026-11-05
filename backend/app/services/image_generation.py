"""Seedream image generation through OpenRouter's dedicated Image API."""
import base64
import io
import logging
import os
import re
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image, ImageOps
from app.core.config import settings
from app.services.generation_errors import MESSAGES

IMAGE_API_URL = 'https://openrouter.ai/api/v1/images'
logger = logging.getLogger(__name__)


class ImageGenerationError(RuntimeError):
    def __init__(self, code, status_code=None, request_id=None):
        self.code = code
        self.status_code = status_code
        self.model = settings.IMAGE_MODEL
        # Never copy a provider response body, prompt, data URL or credential.
        self.request_id = request_id if isinstance(request_id, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', request_id) else None
        if self.request_id and settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY in self.request_id:
            self.request_id = None
        super().__init__(MESSAGES[code])


def provider_error(code, response=None):
    error = ImageGenerationError(code, response.status_code if response is not None else None,
        response.headers.get('x-request-id') if response is not None else None)
    logger.warning('Image generation failed code=%s http=%s model=%s request_id=%s',
        error.code, error.status_code, error.model, error.request_id)
    return error


async def generate_image(prompt: str, output: Path, aspect_ratio: str = '16:9') -> Path:
    if not settings.OPENROUTER_API_KEY:
        raise ImageGenerationError('image_auth_error')
    if not prompt.strip():
        raise ValueError('Rasm topshirig‘i bo‘sh')
    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.post(IMAGE_API_URL,
                headers={'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'HTTP-Referer': settings.FRONTEND_URL, 'X-Title': 'Orzu'},
                json={'model': settings.IMAGE_MODEL, 'prompt': prompt, 'n': 1,
                    'resolution': '1K', 'aspect_ratio': aspect_ratio})
    except httpx.TimeoutException:
        raise provider_error('image_timeout') from None
    except httpx.RequestError:
        raise provider_error('image_network_error') from None
    if not response.is_success:
        code = {401: 'image_auth_error', 403: 'image_auth_error', 402: 'image_credit_exhausted',
                404: 'image_model_unavailable', 429: 'image_rate_limit'}.get(response.status_code,
                'image_provider_error' if response.status_code >= 500 else 'image_request_error')
        raise provider_error(code, response)
    try:
        body = response.json()
    except ValueError:
        raise provider_error('image_invalid_response', response) from None
    entries = body.get('data') if isinstance(body, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict) or not isinstance(entries[0].get('b64_json'), str):
        raise provider_error('image_invalid_response', response)
    encoded = entries[0]['b64_json']
    if len(encoded) > 24 * 1024 * 1024:
        raise ImageGenerationError('image_invalid_data')
    try:
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as picture:
            if picture.format not in {'PNG', 'JPEG', 'WEBP'} or picture.width * picture.height > 20_000_000:
                raise ValueError('Invalid image dimensions')
            normalized = ImageOps.exif_transpose(picture).convert('RGB')
    except (ValueError, OSError, Image.DecompressionBombError):
        raise ImageGenerationError('image_invalid_data') from None
    output = Path(output)
    temporary = output.with_name(f'.{output.name}.{uuid4().hex}.tmp')
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(temporary, format='PNG')
        os.replace(temporary, output)
    except OSError:
        raise ImageGenerationError('image_storage_error') from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return output
