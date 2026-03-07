"""
PDF Generator
=============
PPTX fayldan PDF yasaydi — LibreOffice orqali konvertatsiya.
Alternativ: reportlab bilan to'g'ridan-to'g'ri PDF yasash.
"""

import asyncio
import os
import subprocess
import shutil
from pathlib import Path


async def generate_pdf_from_pptx(pptx_path: str, output_path: str) -> str:
    """
    PPTX → PDF konvertatsiya.
    LibreOffice headless rejimida ishlatiladi.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # LibreOffice yo'lini tekshirish
    soffice_cmd = _find_soffice()
    if not soffice_cmd:
        raise RuntimeError(
            "LibreOffice topilmadi. O'rnating: apt install libreoffice"
        )

    # Vaqtinchalik papka (LibreOffice shu yerga chiqaradi)
    tmp_dir = os.path.dirname(output_path)

    process = await asyncio.create_subprocess_exec(
        soffice_cmd,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", tmp_dir,
        pptx_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

    if process.returncode != 0:
        raise RuntimeError(f"LibreOffice xatosi: {stderr.decode().strip()}")

    # LibreOffice fayl nomini o'zgartirib chiqaradi (presentation_id.pdf)
    pptx_stem = Path(pptx_path).stem
    generated_pdf = os.path.join(tmp_dir, f"{pptx_stem}.pdf")

    if not os.path.exists(generated_pdf):
        raise RuntimeError(f"PDF fayl topilmadi: {generated_pdf}")

    # Kutilgan nom bilan saqlaymiz
    if generated_pdf != output_path:
        shutil.move(generated_pdf, output_path)

    return output_path


def _find_soffice() -> str | None:
    """LibreOffice bajariladigan faylni topadi."""
    candidates = [
        "soffice",
        "libreoffice",
        "/usr/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
        "/opt/libreoffice/program/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
    ]
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None


async def generate_pdf_direct(slides_data: list[dict], output_path: str) -> str:
    """
    Fallback: reportlab bilan to'g'ridan-to'g'ri PDF yasash.
    LibreOffice bo'lmagan muhitlarda ishlatiladi.
    """
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SlideTitle", parent=styles["Heading1"],
        fontSize=24, textColor=colors.HexColor("#1E2761"),
        spaceAfter=12,
    )
    bullet_style = ParagraphStyle(
        "SlideBullet", parent=styles["Normal"],
        fontSize=14, leftIndent=20, spaceAfter=8,
        textColor=colors.HexColor("#2d3e6e"),
    )
    notes_style = ParagraphStyle(
        "Notes", parent=styles["Italic"],
        fontSize=10, textColor=colors.grey, spaceAfter=4,
    )

    story = []
    for i, slide in enumerate(slides_data):
        if i > 0:
            story.append(PageBreak())

        story.append(Paragraph(slide["title"], title_style))
        story.append(Spacer(1, 0.15 * inch))

        for bullet in slide.get("bullets", []):
            story.append(Paragraph(f"▸  {bullet}", bullet_style))

        if slide.get("notes"):
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"<i>Izoh: {slide['notes']}</i>", notes_style))

    doc.build(story)
    return output_path
