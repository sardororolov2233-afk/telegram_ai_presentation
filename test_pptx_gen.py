"""
Test skript: yangi template-based PPTX generatorni sinash.
"""
import asyncio
import sys
import os

# Project root ni path ga qo'shamiz
sys.path.insert(0, os.path.dirname(__file__))

from dataclasses import dataclass

@dataclass
class SlideData:
    index: int
    title: str
    bullets: list
    speaker_notes: str = ""
    slide_type: str = "content"


# Test slaydlar
test_slides = [
    SlideData(
        index=0,
        title="Sun'iy Intellekt va Ta'lim",
        bullets=["Kelajak texnologiyalari haqida taqdimot"],
        speaker_notes="Salom, bugun biz AI haqida gaplashamiz.",
        slide_type="title",
    ),
    SlideData(
        index=1,
        title="AI nima?",
        bullets=[
            "Mashina o'rganishi (Machine Learning)",
            "Chuqur o'rganish (Deep Learning)",
            "Tabiiy tilni qayta ishlash (NLP)",
            "Kompyuter ko'rishi (Computer Vision)",
        ],
        speaker_notes="AI ning asosiy yo'nalishlari haqida.",
        slide_type="content",
    ),
    SlideData(
        index=2,
        title="Ta'limda AI",
        bullets=[
            "Shaxsiylashtirilgan ta'lim dasturlari",
            "Avtomatik baholash tizimlari",
            "Virtual assistentlar va chatbotlar",
            "Adaptiv o'quv platformalari",
        ],
        speaker_notes="Ta'lim sohasida AI qo'llanilishi.",
        slide_type="content",
    ),
    SlideData(
        index=3,
        title="Afzalliklari",
        bullets=[
            "Vaqtni tejash va samaradorlik",
            "Individual yondashuv har bir talabaga",
            "24/7 qo'llab-quvvatlash imkoniyati",
            "Katta hajmdagi ma'lumotlarni tahlil qilish",
        ],
        speaker_notes="AI ning ta'limdagi afzalliklari.",
        slide_type="content",
    ),
    SlideData(
        index=4,
        title="Xulosa",
        bullets=[
            "AI ta'lim sohasini tubdan o'zgartirmoqda",
            "Kelajakda yanada ko'proq innovatsiyalar kutilmoqda",
            "Har bir o'qituvchi AI vositalarini o'rganishi lozim",
        ],
        speaker_notes="Yakuniy xulosalar.",
        slide_type="conclusion",
    ),
]


def test_all_templates():
    """Barcha 10 ta shablonni sinab ko'rish."""
    from pptx_generator import _build_presentation

    output_dir = os.path.join(os.path.dirname(__file__), "test_outputs")
    os.makedirs(output_dir, exist_ok=True)

    success = 0
    failed = 0

    for i in range(1, 11):
        output_path = os.path.join(output_dir, f"test_dizayn_{i}.pptx")
        try:
            _build_presentation(test_slides, output_path, template_index=i)
            file_size = os.path.getsize(output_path)
            print(f"  ✓ dizayn_ {i}.pptx → {output_path} ({file_size // 1024} KB)")
            success += 1
        except Exception as e:
            print(f"  ✗ dizayn_ {i}.pptx → XATO: {e}")
            failed += 1

    print(f"\nNatija: {success} muvaffaqiyat, {failed} xato")


if __name__ == "__main__":
    print("=== PPTX Generator Test ===\n")
    test_all_templates()
    print("\nTest yakunlandi!")
