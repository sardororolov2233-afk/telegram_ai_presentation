"""A single template-based presentation product. One deck consumes one allowance."""
import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4
from app.core.config import settings
from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.pptx_generator import generate_template_pptx
from app.services.presentation.telegram_sender import send_presentation_to_telegram
from app.services.presentation.image_fetcher import fetch_images_for_slides, cleanup_images, reuse_images
from app.services.presentation.subject_templates import canonical_subject, is_subject_pack, load_manifest


class PresentationPipeline:
    def __init__(self):
        self.ai = AIContentGenerator()

    async def run(self, topic: str, language: str = 'uz', author: str = '',
                  subject: str = 'minimalizm', variant: int = 1, bibliography_type: str = 'none',
                  bibliography_text: Optional[str] = None, document_format: str = 'ppt',
                  telegram_id: Optional[int] = None, user_images: Optional[list] = None,
                  request_id: Optional[str] = None) -> dict:
        subject = canonical_subject(subject)
        if not is_subject_pack(subject):
            raise ValueError('Fan shablonini tanlang')
        manifest = load_manifest(subject, variant)
        directory = Path(settings.JOB_STORAGE_DIR) / 'outputs'
        directory.mkdir(parents=True, exist_ok=True)
        presentation_id = str(uuid4())
        cache_dir = Path(settings.JOB_STORAGE_DIR) / 'images' / str(request_id or presentation_id)
        output = directory / f'{presentation_id}.pptx'
        fetched = []
        final_path = output
        try:
            content, keywords = await self.ai.generate_template_slides(topic=topic, author=author,
                language=language, plan_count=manifest['plan_count'], bibliography_type=bibliography_type,
                bibliography_text=bibliography_text, subject=subject, variant=variant)
            if user_images:
                images = reuse_images(user_images, len(manifest['image_slots']))
            else:
                fetched = await fetch_images_for_slides(keywords, cache_dir=cache_dir) if keywords else []
                images = reuse_images(fetched, len(manifest['image_slots']))
            output_path, slide_count = await generate_template_pptx(content, str(output), user_images=images,
                subject=subject, variant=variant, plan_count=manifest['plan_count'], bibliography_type=bibliography_type)
            if document_format == 'pdf':
                from app.services.presentation.pdf_converter import convert_pptx_to_pdf
                final_path = Path(await asyncio.to_thread(convert_pptx_to_pdf, output_path))
            if not final_path.is_file() or not final_path.stat().st_size:
                raise RuntimeError('Taqdimot fayli yaratilmadi')
            sent = False
            if telegram_id:
                try:
                    sent = await send_presentation_to_telegram(telegram_id, topic, str(final_path), slide_count)
                except Exception:
                    # The authenticated job download remains available even if Telegram is down.
                    sent = False
            return {'id': presentation_id, 'telegram_sent': sent, 'slide_count': slide_count,
                'document_path': str(final_path)}
        except BaseException:
            output.unlink(missing_ok=True)
            if final_path != output:
                final_path.unlink(missing_ok=True)
            raise
        finally:
            # Durable job images survive cancellation and lost leases. The worker removes them
            # only after the outcome is committed to Postgres.
            if request_id is None:
                cleanup_images(fetched)
                shutil.rmtree(cache_dir, ignore_errors=True)
