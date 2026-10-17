"""Fill the subject pack selected by the customer. There are no quality tiers."""
import asyncio
import logging
from pathlib import Path
from app.services.presentation.subject_templates import ROOT, canonical_subject, load_manifest, validate_payload
from app.services.presentation.fill_template import fill_template
from app.services.presentation.pptx_assets import optimize_pptx


async def generate_template_pptx(slides_data, output_path, user_images=None, subject='minimalizm', variant=1,
                                 plan_count=4, bibliography_type='none'):
    subject = canonical_subject(subject)
    manifest = load_manifest(subject, variant)
    template_path = ROOT / subject / manifest['template']
    if not template_path.is_file():
        raise FileNotFoundError(f'Shablon topilmadi: {subject} #{variant}')
    validate_payload(slides_data, subject, variant)
    images = {slot['key']: path for slot, path in zip(manifest['image_slots'], user_images or [])
        if path and Path(path).is_file()}
    await asyncio.to_thread(fill_template, str(template_path), slides_data, output_path, images, True)
    try:
        await asyncio.to_thread(optimize_pptx, output_path)
    except (OSError, ValueError):
        # Some supplied legacy decks contain images PowerPoint accepts but PIL cannot recompress.
        # The filled deck already exists; compression must not destroy an otherwise usable result.
        logging.getLogger(__name__).warning('Keeping the uncompressed supplied template: %s #%s', subject, variant)
    return output_path, manifest['slide_count']
