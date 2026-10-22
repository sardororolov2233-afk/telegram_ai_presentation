"""Generate design variants with the same Seedream model as presentations."""
from pathlib import Path
from uuid import uuid4
from app.core.config import settings
from app.services.image_generation import generate_image

STATIC_DIR = str(Path(settings.JOB_STORAGE_DIR) / 'designs')
ASPECT_RATIOS = {'instagram': '1:1', 'telegram': '4:3', 'story': '9:16'}


async def generate_image_with_seedream(prompt: str, format: str, variant_index: int = 0) -> str:
    filename = f'design_{uuid4().hex}.png'
    await generate_image(prompt, Path(STATIC_DIR) / filename, ASPECT_RATIOS[format])
    return filename
