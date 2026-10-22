"""Seedream image generation through OpenRouter's dedicated Image API."""
import base64
import io
import os
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image, ImageOps
from app.core.config import settings

IMAGE_API_URL = 'https://openrouter.ai/api/v1/images'


async def generate_image(prompt: str, output: Path, aspect_ratio: str = '16:9') -> Path:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError('OPENROUTER_API_KEY sozlanmagan')
    if not prompt.strip():
        raise ValueError('Rasm topshirig‘i bo‘sh')
    async with httpx.AsyncClient(timeout=240.0) as client:
        response = await client.post(IMAGE_API_URL,
            headers={'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                'HTTP-Referer': settings.FRONTEND_URL, 'X-Title': 'Orzu'},
            json={'model': settings.IMAGE_MODEL, 'prompt': prompt, 'n': 1,
                'resolution': '1K', 'aspect_ratio': aspect_ratio})
        response.raise_for_status()
    entries = response.json().get('data') or []
    if not entries or not isinstance(entries[0].get('b64_json'), str):
        raise ValueError('Seedream javobida rasm yo‘q')
    encoded = entries[0]['b64_json']
    if len(encoded) > 24 * 1024 * 1024:
        raise ValueError('AI rasmi juda katta')
    raw = base64.b64decode(encoded, validate=True)
    with Image.open(io.BytesIO(raw)) as picture:
        if picture.format not in {'PNG', 'JPEG', 'WEBP'} or picture.width * picture.height > 20_000_000:
            raise ValueError('AI rasm formati yoki o‘lchami noto‘g‘ri')
        normalized = ImageOps.exif_transpose(picture).convert('RGB')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f'.{output.name}.{uuid4().hex}.tmp')
    try:
        normalized.save(temporary, format='PNG')
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
