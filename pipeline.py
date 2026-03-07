"""
Presentation Pipeline
=====================
Barcha servislarni birlashtiruvchi asosiy orchestrator.

Oqim:
  frontend ma'lumotlari
      ↓
  AIContentGenerator  → SlideData[]
      ↓
  HTMLGenerator       → html_preview (string)
      ↓
  PptxGenerator       → presentation.pptx
      ↓
  PdfGenerator        → presentation.pdf
      ↓
  TelegramSender      → foydalanuvchi Telegram'iga yuboradi
"""

import uuid
import os
from typing import Optional

from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.html_generator import generate_html_preview
from app.services.presentation.pptx_generator import generate_pptx
from app.services.presentation.pdf_generator import generate_pdf_from_pptx, generate_pdf_direct
from app.services.presentation.telegram_sender import send_presentation_to_telegram

PRESENTATIONS_DIR = "/tmp/presentations"


class PresentationPipeline:
    """
    To'liq pipeline: frontend → AI → HTML → PPTX → PDF → Telegram.
    """

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
        telegram_id: Optional[int] = None,
    ) -> dict:
        presentation_id = str(uuid.uuid4())[:12]
        pptx_path = f"{PRESENTATIONS_DIR}/{presentation_id}.pptx"
        pdf_path = f"{PRESENTATIONS_DIR}/{presentation_id}.pdf"

        # ── 1. AI → Slayd mazmuni ────────────────────────────────────────
        print(f"[Pipeline] AI mazmun generatsiya: '{topic}'")
        slides = await self.ai.generate_slides(
            topic=topic,
            language=language,
            slide_count=slide_count,
            style=style,
            extra_context=extra_context,
        )
        print(f"[Pipeline] {len(slides)} ta slayd generatsiya qilindi")

        # ── 2. HTML preview ───────────────────────────────────────────────
        print(f"[Pipeline] HTML preview yasalyapti...")
        html_preview = generate_html_preview(slides, topic, style)

        # HTML faylni ham saqlaymiz (ixtiyoriy)
        html_path = f"{PRESENTATIONS_DIR}/{presentation_id}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_preview)

        # ── 3. PPTX ───────────────────────────────────────────────────────
        print(f"[Pipeline] PPTX yasalyapti...")
        try:
            await generate_pptx(slides, pptx_path, style)
            pptx_ok = True
        except Exception as e:
            print(f"[Pipeline] PPTX xatosi: {e}")
            pptx_ok = False

        # ── 4. PDF ────────────────────────────────────────────────────────
        print(f"[Pipeline] PDF yasalyapti...")
        try:
            if pptx_ok:
                await generate_pdf_from_pptx(pptx_path, pdf_path)
            else:
                # Fallback: reportlab bilan to'g'ridan-to'g'ri
                slides_dicts = [
                    {"title": s.title, "bullets": s.bullets, "notes": s.speaker_notes}
                    for s in slides
                ]
                await generate_pdf_direct(slides_dicts, pdf_path)
            pdf_ok = True
        except Exception as e:
            print(f"[Pipeline] PDF xatosi: {e}")
            pdf_ok = False

        # ── 5. Telegram ───────────────────────────────────────────────────
        telegram_sent = False
        if telegram_id:
            print(f"[Pipeline] Telegram ga yuborilyapti: {telegram_id}")
            try:
                await send_presentation_to_telegram(
                    telegram_id=telegram_id,
                    topic=topic,
                    pptx_path=pptx_path if pptx_ok else "",
                    pdf_path=pdf_path if pdf_ok else "",
                    slide_count=len(slides),
                )
                telegram_sent = True
            except Exception as e:
                print(f"[Pipeline] Telegram xatosi: {e}")

        # ── Natija ────────────────────────────────────────────────────────
        print(f"[Pipeline] Tayyor! ID: {presentation_id}")
        return {
            "id": presentation_id,
            "html_preview": html_preview,
            "pptx_url": f"/api/v1/presentations/download/{presentation_id}/pptx" if pptx_ok else "",
            "pdf_url": f"/api/v1/presentations/download/{presentation_id}/pdf" if pdf_ok else "",
            "telegram_sent": telegram_sent,
            "slide_count": len(slides),
        }
