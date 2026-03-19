import uuid
import os
from typing import Optional

from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.pptx_generator import generate_pptx
from app.services.presentation.telegram_sender import send_presentation_to_telegram
from app.services.presentation.image_fetcher import fetch_images_for_slides

PRESENTATIONS_DIR = "/tmp/presentations"


class PresentationPipeline:

    def __init__(self):
        self.ai = AIContentGenerator()
        os.makedirs(PRESENTATIONS_DIR, exist_ok=True)

    async def run(
        self,
        topic: str,
        language: str = "uz",
        slide_count: int = 8,
        style: str = "professional",
        extra_context: Optional[str] = None,
        design_template: int = 1,
        telegram_id: Optional[int] = None,
        user_images: Optional[list] = None,
    ) -> dict:
        presentation_id = str(uuid.uuid4())[:12]
        pptx_path = f"{PRESENTATIONS_DIR}/{presentation_id}.pptx"

        # 1. AI → Slayd mazmuni
        print(f"[Pipeline] AI mazmun generatsiya: '{topic}'")
        slides = await self.ai.generate_slides(
            topic=topic,
            language=language,
            slide_count=slide_count,
            style=style,
            extra_context=extra_context,
        )
        print(f"[Pipeline] {len(slides)} ta slayd generatsiya qilindi")

        # 2. Rasmlarni tayyorlash
        if user_images:
            final_images = user_images
            print(f"[Pipeline] User rasmlari: {len(final_images)} ta")
        else:
            print(f"[Pipeline] Unsplash dan rasmlar olinmoqda...")
            try:
                final_images = await fetch_images_for_slides(topic, slide_count)
            except Exception as e:
                print(f"[Pipeline] Unsplash xatosi: {e}")
                final_images = []

        # 3. PPTX
        print(f"[Pipeline] PPTX yasalyapti...")
        try:
            await generate_pptx(
                slides=slides,
                output_path=pptx_path,
                style=style,
                template_index=design_template,
                user_images=final_images,
            )
            pptx_ok = True
        except Exception as e:
            print(f"[Pipeline] PPTX xatosi: {e}")
            pptx_ok = False

        # 4. Telegram
        telegram_sent = False
        if telegram_id:
            print(f"[Pipeline] Telegram ga yuborilyapti: {telegram_id}")
            try:
                await send_presentation_to_telegram(
                    telegram_id=telegram_id,
                    topic=topic,
                    pptx_path=pptx_path if pptx_ok else "",
                    slide_count=len(slides),
                )
                telegram_sent = True
            except Exception as e:
                print(f"[Pipeline] Telegram xatosi: {e}")

        print(f"[Pipeline] Tayyor! ID: {presentation_id}")
        return {
            "id": presentation_id,
            "pptx_url": f"/api/v1/presentations/download/{presentation_id}/pptx" if pptx_ok else "",
            "telegram_sent": telegram_sent,
            "slide_count": len(slides),
        }