"""
PPTX Generator — Template-based
================================
10 ta tayyor dizayn shablonidan foydalanib SlideData ro'yxatidan
professional PPTX fayl yasaydi.

Yondashuv:
  1. Tanlangan shablon faylni yuklash (dizayn_ 1..10.pptx)
  2. Birinchi slayd = title slide dizayni sifatida ishlatiladi
  3. Ikkinchi slayddan boshlab content slide sifatida nusxalanadi
  4. Asl shablon slaydlarini o'chirish, faqat yangi slaydlar qoladi
"""

import os
import copy
import random
import asyncio
from pathlib import Path
from typing import Optional

from pptx import Presentation
from pptx.util import Pt

try:
    from app.services.presentation.ai_generator import SlideData
except ImportError:
    from dataclasses import dataclass

    @dataclass
    class SlideData:
        index: int
        title: str
        bullets: list
        speaker_notes: str = ""
        slide_type: str = "content"

# Shablonlar papkasi
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_template_path(template_index: Optional[int] = None) -> str:
    """Shablon faylni tanlash. Agar index berilmasa, tasodifiy tanlanadi."""
    if template_index is None:
        template_index = random.randint(1, 10)
    template_index = max(1, min(10, template_index))
    path = TEMPLATES_DIR / f"dizayn_ {template_index}.pptx"
    if not path.exists():
        for i in range(1, 11):
            fallback = TEMPLATES_DIR / f"dizayn_ {i}.pptx"
            if fallback.exists():
                return str(fallback)
        raise FileNotFoundError(f"Templates papkasida shablon topilmadi: {TEMPLATES_DIR}")
    return str(path)


def _clone_slide(prs: Presentation, template_slide) -> object:
    """
    Template slaydni XML darajasida klonlaydi.
    Barcha shape, background, rasm va boshqa elementlarni saqlaydi.
    """
    slide_layout = template_slide.slide_layout
    new_slide = prs.slides.add_slide(slide_layout)

    # Yangi slaydning spTree ichidagi barcha shape elementlarni o'chirish
    sp_tree = new_slide.shapes._spTree
    tags_to_remove = ['}sp', '}pic', '}grpSp', '}cxnSp']
    for sp in list(sp_tree):
        if any(sp.tag.endswith(t) for t in tags_to_remove):
            sp_tree.remove(sp)

    # Template slayddagi barcha elementlarni nusxalash
    tmpl_sp_tree = template_slide.shapes._spTree
    for sp in tmpl_sp_tree:
        if any(sp.tag.endswith(t) for t in tags_to_remove):
            new_sp = copy.deepcopy(sp)
            sp_tree.append(new_sp)

    # Background elementini nusxalash
    try:
        P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
        tmpl_cSld = template_slide._element.find(f'{{{P_NS}}}cSld')
        new_cSld = new_slide._element.find(f'{{{P_NS}}}cSld')
        if tmpl_cSld is not None and new_cSld is not None:
            tmpl_bg = tmpl_cSld.find(f'{{{P_NS}}}bg')
            if tmpl_bg is not None:
                old_bg = new_cSld.find(f'{{{P_NS}}}bg')
                new_bg = copy.deepcopy(tmpl_bg)
                if old_bg is not None:
                    new_cSld.replace(old_bg, new_bg)
                else:
                    new_cSld.insert(0, new_bg)
    except Exception:
        pass

    # Relationship'larni nusxalash (rasmlar uchun)
    try:
        for rel in template_slide.part.rels.values():
            if "image" in rel.reltype:
                new_slide.part.rels.get_or_add(rel.reltype, rel._target)
    except Exception:
        pass

    return new_slide


def _find_text_shapes(slide) -> list:
    """Slayddagi barcha matnli shape'larni topish."""
    return [shape for shape in slide.shapes if shape.has_text_frame]


def _inject_title(slide, title: str):
    """Title matnini slaydga yozish."""
    # Avval placeholder orqali
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == 0:
            shape.text = title
            return
    # Fallback: birinchi text shape
    text_shapes = _find_text_shapes(slide)
    if text_shapes:
        text_shapes[0].text = title


def _inject_bullets(slide, bullets: list, title: str = ""):
    """Bullet pointlarni slaydga yozish."""
    # Body placeholder (idx=1 yoki idx=2)
    for ph_idx in [1, 2]:
        for shape in slide.placeholders:
            if shape.placeholder_format.idx == ph_idx and shape.has_text_frame:
                tf = shape.text_frame
                tf.clear()
                for i, bullet in enumerate(bullets):
                    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    para.text = bullet
                    para.level = 0
                return

    # Fallback: ikkinchi text shape
    text_shapes = _find_text_shapes(slide)
    content_shapes = [s for s in text_shapes if s.text != title]
    if not content_shapes and len(text_shapes) > 1:
        content_shapes = text_shapes[1:]

    if content_shapes:
        tf = content_shapes[0].text_frame
        tf.clear()
        for i, bullet in enumerate(bullets):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = bullet
            para.level = 0


def _inject_notes(slide, notes: str):
    """Speaker notes qo'shish."""
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def _delete_slide(prs: Presentation, slide_index: int):
    """Slaydni o'chirish."""
    rId = prs.slides._sldIdLst[slide_index].rId
    prs.part.drop_rel(rId)
    del prs.slides._sldIdLst[slide_index]


def _build_presentation(
    slides: list,
    output_path: str,
    template_index: Optional[int] = None,
) -> str:
    """
    Asosiy PPTX qurish funksiyasi.
    1. Shablonni yuklaydi
    2. Har bir SlideData uchun mos slayd nusxalaydi
    3. Matnlarni joylashtiradi
    4. Asl shablon slaydlarni o'chiradi
    5. Faylni saqlaydi
    """
    template_path = _get_template_path(template_index)
    print(f"[PptxGen] Shablon: {template_path}")

    prs = Presentation(template_path)
    original_count = len(prs.slides)

    print(f"[PptxGen] Shablon slaydlar: {original_count}, Generatsiya: {len(slides)}")

    # Shablondagi slaydlarni xotirada saqlash
    tmpl_slides = list(prs.slides)
    title_tmpl = tmpl_slides[0] if tmpl_slides else None
    content_tmpl = tmpl_slides[1] if len(tmpl_slides) > 1 else title_tmpl

    # Har bir SlideData uchun yangi slayd
    for sd in slides:
        if sd.slide_type == "title" and title_tmpl:
            new_slide = _clone_slide(prs, title_tmpl)
        elif content_tmpl:
            new_slide = _clone_slide(prs, content_tmpl)
        else:
            new_slide = prs.slides.add_slide(prs.slide_layouts[0])

        _inject_title(new_slide, sd.title)
        if sd.bullets:
            _inject_bullets(new_slide, sd.bullets, sd.title)
        if sd.speaker_notes:
            try:
                _inject_notes(new_slide, sd.speaker_notes)
            except Exception:
                pass

    # Asl shablon slaydlarni o'chirish (oxiridan boshlab)
    for i in range(original_count - 1, -1, -1):
        _delete_slide(prs, i)

    # Saqlash
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    prs.save(output_path)
    print(f"[PptxGen] Saqlandi: {output_path}")
    return output_path


async def generate_pptx(
    slides: list,
    output_path: str,
    style: str = "professional",
    template_index: Optional[int] = None,
) -> str:
    """
    PPTX fayl yasaydi va yo'lini qaytaradi.

    Args:
        slides: SlideData ro'yxati
        output_path: Natija PPTX fayl yo'li
        style: Dizayn stili (template o'zi stil beradi)
        template_index: Shablon raqami (1-10), None bo'lsa tasodifiy
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _build_presentation,
        slides,
        output_path,
        template_index,
    )
    return result
