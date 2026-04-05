import uuid
import os
import traceback
from typing import Optional

from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.pptx_generator import generate_pptx
from app.services.presentation.telegram_sender import send_presentation_to_telegram
from app.services.presentation.image_fetcher import fetch_images_for_slides, cleanup_images

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

        print(f"[Pipeline] AI mazmun generatsiya: '{topic}'")
        slides = await self.ai.generate_slides(
            topic=topic,
            language=language,
            slide_count=slide_count,
            style=style,
            extra_context=extra_context,
        )
        print(f"[Pipeline] {len(slides)} ta slayd generatsiya qilindi")

        if user_images:
            final_images = []
            while len(final_images) < len(slides):
                final_images.extend(user_images)
            final_images = final_images[:len(slides)]
        else:
            try:
                keywords = []
                for s in slides:
                    kw = s.image_keyword if s.image_keyword else f"{topic} professional presentation concept"
                    keywords.append(kw)
                final_images = await fetch_images_for_slides(keywords)
            except Exception as e:
                print(f"[Pipeline] Rasm yuklash xatosi: {e}")
                final_images = [None] * len(slides)

        # Faqat biz yuklaganlarni kuzatamiz (user_images bo'lsa ularni o'chirmaymiz)
        _fetched_images = final_images if not user_images else []

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
            traceback.print_exc()  # To'liq xato izini ko'rsatish
            pptx_ok = False
        finally:
            # Vaqtinchalik rasmlarni PPTX dan keyin o'chirish
            if _fetched_images:
                cleanup_images(_fetched_images)
                print(f"[Pipeline] {len(_fetched_images)} ta vaqtinchalik rasm o'chirildi")

        telegram_sent = False
        if telegram_id and pptx_ok:
            try:
                await send_presentation_to_telegram(
                    telegram_id=telegram_id,
                    topic=topic,
                    pptx_path=pptx_path,
                    slide_count=len(slides),
                )
                telegram_sent = True
            except Exception as e:
                print(f"[Pipeline] Telegram xatosi: {e}")
            finally:
                # Faylni o'chirish � Telegram ga yuborilgandan keyin kerak emas
                try:
                    os.remove(pptx_path)
                except Exception:
                    pass

        return {
            "id": presentation_id,
            "telegram_sent": telegram_sent,
            "slide_count": len(slides),
        }
