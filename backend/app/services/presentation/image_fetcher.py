"""At most three Seedream requests per deck, including worker restarts."""
import logging
from pathlib import Path
from uuid import uuid4
from app.core.config import settings
from app.services.image_generation import generate_image

logger = logging.getLogger(__name__)


def cleanup_images(image_paths: list) -> None:
    for path in set(filter(None, image_paths)):
        Path(path).unlink(missing_ok=True)


async def fetch_images_for_slides(keywords: list, cache_dir: Path | None = None) -> list[str]:
    directory = Path(cache_dir) if cache_dir else Path(settings.JOB_STORAGE_DIR) / 'images' / uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    prompts = list(dict.fromkeys(str(q).strip() for q in keywords if q and str(q).strip()))[:settings.PRESENTATION_MAX_IMAGES]
    images = []
    for index, prompt in enumerate(prompts):
        output = directory / f'image_{index}.png'
        if output.is_file():
            images.append(str(output))
            continue
        # Reserve an attempt before calling the provider. A crash with an unknown API result must
        # not trigger a fourth paid request when another worker claims the durable job.
        try:
            with (directory / f'image_{index}.requested').open('x') as marker:
                marker.write(settings.IMAGE_MODEL)
        except FileExistsError:
            continue
        try:
            await generate_image(prompt, output)
            images.append(str(output))
        except Exception:
            logger.warning('Seedream image %s failed; reuse successful deck images', index + 1)
    if prompts and not images:
        raise RuntimeError('Taqdimot rasmlarini yaratib bo‘lmadi')
    return images


def reuse_images(images: list, slot_count: int) -> list[str]:
    """Keep related neighboring template slots on the same visual; crop to each slot."""
    available = list(dict.fromkeys(filter(None, images)))[:settings.PRESENTATION_MAX_IMAGES]
    if not available or not slot_count:
        return []
    return [available[min(len(available) - 1, index * len(available) // slot_count)]
        for index in range(slot_count)]
