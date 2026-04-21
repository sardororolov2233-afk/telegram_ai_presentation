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
        is_pro: bool = False,
        author: Optional[str] = None,
        pro_plan_count: int = 5,
        pro_bibliography_type: str = "none",
        pro_bibliography_text: Optional[str] = None,
        pro_design: Optional[str] = None,
        pro_design_variant: int = 1,
    ) -> dict:
        presentation_id = str(uuid.uuid4())[:12]
        pptx_path = f"{PRESENTATIONS_DIR}/{presentation_id}.pptx"

        if is_pro:
            print(f"[Pipeline] AI mazmun generatsiya (PRO): '{topic}' | Shablon: {pro_design} #{pro_design_variant}")
            slides_dict, pro_keywords = await self.ai.generate_pro_slides(
                topic=topic,
                author=author or "Foydalanuvchi",
                language=language,
                pro_plan_count=pro_plan_count,
                pro_bibliography_type=pro_bibliography_type,
                pro_bibliography_text=pro_bibliography_text,
            )
            slides = slides_dict # For compatibility with other parts if needed
            print(f"[Pipeline] PRO rejimda ma'lumotlar generatsiya qilindi | Bo'lim: {pro_design}, Variant: #{pro_design_variant}")
        else:
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

        elif is_pro:
            # Pro image generation logic
            try:
                from app.services.presentation.pro_image_fetcher import fetch_pro_images_with_gemini
                kw_to_fetch = pro_keywords if 'pro_keywords' in locals() else [f"{topic} professional presentation"] * 5
                final_images = await fetch_pro_images_with_gemini(kw_to_fetch[:5])
            except Exception as e:
                print(f"[Pipeline] PRO Rasm yuklash xatosi: {e}")
                final_images = []
        else:
            # Standart rasm yuklash
            try:
                keywords = []
                for s in slides:
                    kw = s.image_keyword if hasattr(s, 'image_keyword') and s.image_keyword else f"{topic} professional presentation concept"
                    keywords.append(kw)
                from app.services.presentation.image_fetcher import fetch_images_for_slides
                final_images = await fetch_images_for_slides(keywords)
            except Exception as e:
                print(f"[Pipeline] Rasm yuklash xatosi: {e}")
                final_images = [None] * len(slides)

        # Faqat biz yuklaganlarni kuzatamiz (user_images bo'lsa ularni o'chirmaymiz)
        _fetched_images = final_images if not user_images else []

        try:
            if is_pro:
                from app.services.presentation.pptx_generator import generate_pro_pptx
                pptx_path_res, total_slides = await generate_pro_pptx(
                    slides_data=slides_dict,
                    output_path=pptx_path,
                    user_images=final_images,
                    pro_design=pro_design,
                    pro_design_variant=pro_design_variant,
                )
            else:
                pptx_path_res, total_slides = await generate_pptx(
                    slides=slides,
                    output_path=pptx_path,
                    style=style,
                    template_index=design_template,
                    user_images=final_images,
                )
            # Update pptx_path just in case (though it should be the same)
            pptx_path = pptx_path_res
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
                    slide_count=total_slides if 'total_slides' in locals() else len(slides),
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
