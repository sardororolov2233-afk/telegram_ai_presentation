"""
Taqdimot Generatsiya Pipeline (Professional Multi-Stage)
=========================================================
Oqim:
  1. Outline Generator  → slayd turlarini aniqlash
  2. Content Generator   → har bir slayd uchun mazmun yaratish (parallel)
  3. Image Fetcher       → Unsplash rasmlar (max 5)
  4. Template Engine     → HTML / PPTX / PDF yaratish
  5. Telegram            → fayllarni yuborish
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Optional


# ──────────────────────────────────────────────────────────────
# 10 ta tayyor dizayn shablonlari
# ──────────────────────────────────────────────────────────────

DESIGN_TEMPLATES: dict[int, dict] = {
    1: {  # Minimalist Macaron
        "page_bg": "#ffffff", "slide_bg": "#ffffff",
        "title_color": "#1a1a1a", "body_color": "#333333",
        "accent": "#c8e6c9", "num_color": "#999999",
        "font": "'Segoe UI', sans-serif", "theme_name": "Minimalist Macaron",
    },
    2: {  # Classic Architecture
        "page_bg": "#3a3228", "slide_bg": "#4b4537",
        "title_color": "#ffffff", "body_color": "#e0dcd4",
        "accent": "#c9b896", "num_color": "#8a8070",
        "font": "'Segoe UI', sans-serif", "theme_name": "Classic Architecture",
    },
    3: {  # Abstract Lines
        "page_bg": "#f5f5f5", "slide_bg": "#f5f5f5",
        "title_color": "#37474f", "body_color": "#546e7a",
        "accent": "#bca88e", "num_color": "#90a4ae",
        "font": "Arial, sans-serif", "theme_name": "Abstract Lines",
    },
    4: {  # Financial Modern
        "page_bg": "#0f2944", "slide_bg": "#1a3a5f",
        "title_color": "#ffffff", "body_color": "#b0c4de",
        "accent": "#00bcd4", "num_color": "#5a7fa0",
        "font": "'Calibri', sans-serif", "theme_name": "Financial Modern",
    },
    5: {  # Nature Adventure
        "page_bg": "#1b2a1b", "slide_bg": "#2d4a2d",
        "title_color": "#ffffff", "body_color": "#c8e6c9",
        "accent": "#66bb6a", "num_color": "#5a7a5a",
        "font": "'Brush Script MT', cursive, sans-serif", "theme_name": "Nature Adventure",
    },
    6: {  # Medical Clean
        "page_bg": "#f8f9fa", "slide_bg": "#ffffff",
        "title_color": "#333333", "body_color": "#555555",
        "accent": "#607d8b", "num_color": "#9e9e9e",
        "font": "'Trebuchet MS', sans-serif", "theme_name": "Medical Clean",
    },
    7: {  # Bauhaus Geometric
        "page_bg": "#fce4ec", "slide_bg": "#f8bbd0",
        "title_color": "#1a1a1a", "body_color": "#333333",
        "accent": "#e91e63", "num_color": "#999999",
        "font": "'Playfair Display', serif", "theme_name": "Bauhaus Geometric",
    },
    8: {  # Elegant Emerald
        "page_bg": "#1e2a16", "slide_bg": "#2e3b23",
        "title_color": "#f5f5dc", "body_color": "#c5e1a5",
        "accent": "#8bc34a", "num_color": "#6a7a5a",
        "font": "Georgia, serif", "theme_name": "Elegant Emerald",
    },
    9: {  # Rustic Wood
        "page_bg": "#1a1210", "slide_bg": "#2c1e14",
        "title_color": "#f5e6d0", "body_color": "#d4b896",
        "accent": "#8d6e4c", "num_color": "#6b5a48",
        "font": "'Georgia', serif", "theme_name": "Rustic Wood",
    },
    10: {  # Abstract Geometry
        "page_bg": "#344e6a", "slide_bg": "#4a698d",
        "title_color": "#ffffff", "body_color": "#cfd8dc",
        "accent": "#9c27b0", "num_color": "#7a99b8",
        "font": "'Arial Black', sans-serif", "theme_name": "Abstract Geometry",
    },
}

# Qo'llab-quvvatlanadigan slayd turlari
SLIDE_TYPES = [
    "title", "problem", "solution", "content", "chart",
    "image_text", "comparison", "quote", "team", "closing",
]

GROQ_MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────

class PresentationPipeline:
    """
    Professional multi-stage pipeline:
      1. _generate_outline()       → slayd turlari
      2. _generate_all_content()   → parallel content
      3. _fetch_images()           → Unsplash
      4. _build_html / _build_pptx → render
      5. _send_to_telegram         → yuborish
    """

    def _output_dir(self) -> str:
        d = os.path.join(os.path.expanduser("~"), "presentations_cache")
        os.makedirs(d, exist_ok=True)
        return d

    # ══════════════════════════════════════════════════════════
    # PUBLIC ENTRY POINT
    # ══════════════════════════════════════════════════════════

    async def run(
        self,
        topic: str,
        language: str,
        slide_count: int,
        style: str,
        extra_context: Optional[str],
        telegram_id: Optional[int],
        design_template: int = 1,
    ) -> dict:
        pid = str(uuid.uuid4())
        out = self._output_dir()

        # 1. Dizayn shabloni
        theme = DESIGN_TEMPLATES.get(design_template, DESIGN_TEMPLATES[1]).copy()
        print(f"[Pipeline] Shablon: {theme.get('theme_name', '?')}")

        # 2. Outline — slayd turlarini aniqlash
        outline = await self._generate_outline(topic, language, slide_count, extra_context)
        print(f"[Pipeline] Outline: {len(outline)} slayd turi aniqlandi")

        # 3. Har bir slayd uchun kontent yaratish (parallel)
        slides = await self._generate_all_content(outline, topic, language, extra_context)
        print(f"[Pipeline] Content: {len(slides)} slayd tayyor")

        # 4. Rasmlar (max 5, faqat image_prompt bor slaydlar)
        slides = await self._fetch_images(slides)

        # 5. HTML
        html = self._build_html(topic, slides, theme)
        with open(f"{out}/{pid}.html", "w", encoding="utf-8") as f:
            f.write(html)

        # 6. PPTX
        pptx_path = f"{out}/{pid}.pptx"
        self._build_pptx(topic, slides, theme, pptx_path)

        # 7. PDF
        pdf_path = f"{out}/{pid}.pdf"
        await self._build_pdf_async(topic, slides, theme, pdf_path)

        # 8. Telegram
        tg_sent = False
        if telegram_id:
            tg_sent = await self._send_to_telegram(telegram_id, pptx_path, pdf_path, topic)

        return {
            "id": pid,
            "html_preview": html,
            "pptx_url": f"/api/v1/presentations/download/{pid}/pptx",
            "pdf_url": f"/api/v1/presentations/download/{pid}/pdf",
            "telegram_sent": tg_sent,
            "slide_count": len(slides),
        }

    # ══════════════════════════════════════════════════════════
    # STAGE 1: OUTLINE GENERATOR
    # ══════════════════════════════════════════════════════════

    async def _generate_outline(
        self, topic: str, language: str, slide_count: int, extra_context: Optional[str]
    ) -> list[dict]:
        """AI slayd turlarini aniqlaydi: title, problem, solution, ..."""
        from app.core.config import settings

        if not settings.GROQ_API_KEY:
            return self._default_outline(slide_count)

        extra = f"\nQo'shimcha kontekst: {extra_context}" if extra_context else ""
        types_str = ", ".join(SLIDE_TYPES)

        prompt = f"""Sen professional taqdimot strukturasini yaratuvchi AI yordamchisan.

Mavzu: {topic}{extra}
Slaydlar soni: {slide_count}

Quyidagi slayd turlaridan foydalanib, taqdimot strukturasini yarat:
{types_str}

QOIDALAR:
1. Birinchi slayd DOIM "title" turi bo'lsin
2. Oxirgi slayd DOIM "closing" turi bo'lsin
3. Mavzuga mos turlarni tanla
4. Har xil turlardan foydalanib, qiziqarli struktura yarat

Faqat JSON formatda javob ber:
[
  {{"type": "title", "hint": "Mavzu sarlavhasi va kirish"}},
  {{"type": "problem", "hint": "Muammo tavsifi"}},
  ...
]"""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            resp = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Faqat valid JSON array qaytarasan. Boshqa hech narsa yozma."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=1024,
            )

            raw = resp.choices[0].message.content.strip()
            raw = self._clean_json(raw)
            outline = json.loads(raw)

            # Validatsiya
            validated = []
            for item in outline:
                if isinstance(item, dict) and "type" in item:
                    stype = item["type"] if item["type"] in SLIDE_TYPES else "content"
                    validated.append({"type": stype, "hint": str(item.get("hint", ""))})

            return validated[:slide_count] if validated else self._default_outline(slide_count)

        except Exception as e:
            print(f"[Pipeline] Outline xatosi: {e}")
            return self._default_outline(slide_count)

    def _default_outline(self, count: int) -> list[dict]:
        """Fallback outline."""
        base = [
            {"type": "title", "hint": "Kirish"},
            {"type": "problem", "hint": "Muammo"},
            {"type": "solution", "hint": "Yechim"},
            {"type": "content", "hint": "Asosiy ma'lumot"},
            {"type": "chart", "hint": "Statistika"},
            {"type": "image_text", "hint": "Vizual"},
            {"type": "comparison", "hint": "Solishtirish"},
            {"type": "quote", "hint": "Iqtibos"},
            {"type": "team", "hint": "Jamoa"},
            {"type": "closing", "hint": "Xulosa"},
        ]
        result = base[:count]
        # Doim title bilan boshlash va closing bilan tugash
        if result[0]["type"] != "title":
            result[0] = {"type": "title", "hint": "Kirish"}
        if len(result) > 1 and result[-1]["type"] != "closing":
            result[-1] = {"type": "closing", "hint": "Xulosa"}
        return result

    # ══════════════════════════════════════════════════════════
    # STAGE 2: CONTENT GENERATOR (PARALLEL)
    # ══════════════════════════════════════════════════════════

    async def _generate_all_content(
        self, outline: list[dict], topic: str, language: str, extra_context: Optional[str]
    ) -> list[dict]:
        """Barcha slaydlar uchun parallel content yaratish."""
        tasks = [
            self._generate_slide_content(item, topic, language, extra_context, i, len(outline))
            for i, item in enumerate(outline)
        ]
        slides = await asyncio.gather(*tasks)
        return list(slides)

    async def _generate_slide_content(
        self,
        outline_item: dict,
        topic: str,
        language: str,
        extra_context: Optional[str],
        index: int,
        total: int,
    ) -> dict:
        """Bitta slayd uchun kontent yaratish."""
        from app.core.config import settings

        slide_type = outline_item["type"]
        hint = outline_item.get("hint", "")

        if not settings.GROQ_API_KEY:
            return self._demo_slide(slide_type, topic, hint, index)

        lang_map = {"uz": "O'zbek tilida", "ru": "на русском языке", "en": "in English"}
        lang_str = lang_map.get(language, "in English")
        extra = f"\nQo'shimcha kontekst: {extra_context}" if extra_context else ""

        # Slayd turiga qarab maxsus instruktsiya
        type_instructions = {
            "title": "Kirish slayd. Katta sarlavha va qisqa tavsif (1-2 jumla subtitle). Body kerak emas.",
            "problem": "Muammo slayd. 50-80 so'zlik akademik matn muammoni tavsiflaydi. 3-4 ta asosiy muammo nuqtalari.",
            "solution": "Yechim slayd. 50-80 so'zlik akademik matn yechimni tavsifla. 3-4 ta yechim yo'llari.",
            "content": "Asosiy kontent slayd. 60-100 so'zlik chuqur akademik matn. Ma'lumotli paragraf.",
            "chart": "Statistika slayd. Raqamlar va dalillarga boy matn. Kamida 3-4 ta raqamli ma'lumot (points da).",
            "image_text": "Vizual tushuntirish slayd. 50-80 so'zlik matn + image_prompt berish SHART.",
            "comparison": "Solishtirish slayd. 2 ta narsani solishtiradigan matn. Points da har birining afzalliklari.",
            "quote": "Iqtibos slayd. Mashhur shaxs yoki manba dan iqtibos. body da iqtibos, subtitle da muallif.",
            "team": "Jamoa/tashkilot slayd. Ishtirokchilar yoki tashkilotlar haqida. Points da ro'yxat.",
            "closing": "Xulosa slayd. Asosiy xulosalar va keyingi qadamlar. 3-4 yakuniy fikr.",
        }

        instruction = type_instructions.get(slide_type, "Akademik matn yozing. 50-100 so'z.")

        # image_prompt faqat image_text, problem, solution, content turlarda berish mumkin
        image_note = ""
        if slide_type in ("image_text", "problem", "solution", "content", "title"):
            image_note = '\n"image_prompt" maydonini ham qo\'shing — Unsplash dan rasm izlash uchun ingliz tilida 2-4 so\'zlik tavsif.'

        prompt = f"""Taqdimot slayd kontenti yarat.
Mavzu: {topic}
Slayd turi: {slide_type}
Hint: {hint}
Bu {index + 1}-slayd (jami {total} ta)
Til: {lang_str}{extra}

{instruction}

JSON formatda javob ber:
{{
  "title": "Slayd sarlavhasi",
  "subtitle": "Qo'shimcha sarlavha (ixtiyoriy)",
  "body": "Akademik paragraf matni (50-100 so'z)",
  "points": ["Nuqta 1", "Nuqta 2", "Nuqta 3"],
  "emoji": "🎯"{image_note}
}}

MUHIM: body maydoni 50-100 so'zdan iborat bo'lsin. Points maydoni 3-5 ta qisqa gap."""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            resp = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Faqat valid JSON object qaytarasan. Boshqa hech narsa yozma."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1024,
            )

            raw = resp.choices[0].message.content.strip()
            raw = self._clean_json(raw)

            # { ... } qismini olish
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > 0:
                raw = raw[start:end]

            data = json.loads(raw)

            slide = {
                "type": slide_type,
                "title": str(data.get("title", hint or topic)),
                "subtitle": str(data.get("subtitle", "")),
                "body": str(data.get("body", "")),
                "points": [str(p) for p in data.get("points", [])],
                "emoji": str(data.get("emoji", "📌")),
            }
            if data.get("image_prompt"):
                slide["image_prompt"] = str(data["image_prompt"])

            return slide

        except Exception as e:
            print(f"[Pipeline] Content xatosi (slayd {index + 1}, {slide_type}): {e}")
            return self._demo_slide(slide_type, topic, hint, index)

    def _demo_slide(self, slide_type: str, topic: str, hint: str, index: int) -> dict:
        """Fallback demo slide."""
        emojis = {"title": "🚀", "problem": "⚠️", "solution": "💡", "content": "📖",
                  "chart": "📊", "image_text": "🖼️", "comparison": "⚖️",
                  "quote": "💬", "team": "👥", "closing": "🎯"}
        return {
            "type": slide_type,
            "title": f"{topic}" if slide_type == "title" else hint or slide_type.capitalize(),
            "subtitle": f"{topic} haqida" if slide_type == "title" else "",
            "body": f"{topic} haqida {index + 1}-qism ma'lumoti. Bu demo matn.",
            "points": ["Muhim nuqta 1", "Muhim nuqta 2", "Muhim nuqta 3"],
            "emoji": emojis.get(slide_type, "📌"),
        }

    # ══════════════════════════════════════════════════════════
    # STAGE 3: IMAGE FETCHER
    # ══════════════════════════════════════════════════════════

    async def _fetch_images(self, slides: list[dict]) -> list[dict]:
        """Unsplash dan rasmlar olish (max 5)."""
        image_count = 0
        for slide in slides:
            if slide.get("image_prompt") and image_count < 5:
                q = slide["image_prompt"].replace(" ", ",")
                slide["image_url"] = f"https://source.unsplash.com/800x400/?{q}"
                image_count += 1
            elif "image_prompt" in slide and image_count >= 5:
                del slide["image_prompt"]  # Limit exceeded
        print(f"[Pipeline] Rasmlar: {image_count} ta rasm tayyor")
        return slides

    # ══════════════════════════════════════════════════════════
    # STAGE 4: HTML TEMPLATE ENGINE
    # ══════════════════════════════════════════════════════════

    def _build_html(self, topic: str, slides: list[dict], theme: dict) -> str:
        cfg = theme
        total = len(slides)

        slides_html = ""
        for i, s in enumerate(slides):
            display = "flex" if i == 0 else "none"
            inner = self._render_slide_html(s, cfg)
            slides_html += f"""
        <div class="slide" id="s{i}" style="display:{display}">
            <div class="slide-num">{i+1} / {total}</div>
            {inner}
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._esc(topic)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@400;600;700&family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@400;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: {cfg['font']};
    background: {cfg['page_bg']};
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}

  .deck {{ width: 100%; max-width: 960px; }}

  .slide {{
    background: {cfg['slide_bg']};
    border-radius: 24px;
    padding: 48px 56px;
    min-height: 480px;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    position: relative;
    box-shadow: 0 25px 60px rgba(0,0,0,.35);
    animation: fadeSlide .4s ease;
    border: 1px solid rgba(255,255,255,.06);
  }}

  @keyframes fadeSlide {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  .slide-num {{
    position: absolute; top: 20px; right: 28px;
    font-size: .8rem; color: {cfg['num_color']}; letter-spacing: .05em;
  }}

  .slide-emoji {{ font-size: 2.8rem; margin-bottom: 14px; line-height: 1; }}

  .slide-title {{
    font-size: clamp(1.5rem, 3vw, 2.2rem);
    font-weight: 700; color: {cfg['title_color']};
    line-height: 1.2; margin-bottom: 8px;
  }}

  .slide-subtitle {{
    font-size: clamp(1rem, 1.8vw, 1.3rem);
    color: {cfg['accent']}; margin-bottom: 20px; font-weight: 500;
  }}

  .slide-body {{
    font-size: clamp(.9rem, 1.4vw, 1.05rem);
    color: {cfg['body_color']}; line-height: 1.85; margin-bottom: 16px;
  }}

  .slide-points {{
    list-style: none; padding: 0; margin: 8px 0;
  }}

  .slide-points li {{
    padding: 8px 0 8px 24px; position: relative;
    color: {cfg['body_color']}; font-size: clamp(.9rem, 1.3vw, 1.05rem);
    line-height: 1.6;
  }}

  .slide-points li::before {{
    content: ''; position: absolute; left: 0; top: 50%;
    transform: translateY(-50%); width: 8px; height: 8px;
    border-radius: 50%; background: {cfg['accent']};
  }}

  .slide-image {{
    margin: 16px 0; border-radius: 12px; overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,.25);
  }}

  .slide-image img {{
    width: 100%; max-height: 220px; object-fit: cover; display: block;
  }}

  /* Title slayd */
  .slide--title {{ text-align: center; align-items: center; justify-content: center; }}
  .slide--title .slide-emoji {{ font-size: 4rem; }}
  .slide--title .slide-title {{ font-size: clamp(2rem, 4vw, 3rem); margin-bottom: 16px; }}

  /* Quote slayd */
  .slide--quote .slide-body {{
    font-size: clamp(1.2rem, 2vw, 1.6rem);
    font-style: italic; border-left: 4px solid {cfg['accent']};
    padding-left: 24px; margin: 24px 0;
  }}

  /* Chart slayd */
  .stat-cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }}
  .stat-card {{
    flex: 1; min-width: 140px; padding: 20px; border-radius: 12px;
    background: {cfg['accent']}22; text-align: center;
  }}
  .stat-card .stat-num {{
    font-size: 1.6rem; font-weight: 700; color: {cfg['accent']};
  }}
  .stat-card .stat-label {{
    font-size: .85rem; color: {cfg['body_color']}; margin-top: 4px;
  }}

  /* Comparison slayd */
  .compare-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 16px 0; }}
  .compare-col {{ padding: 20px; border-radius: 12px; background: {cfg['accent']}11; }}

  /* Image-text slayd */
  .img-text-layout {{ display: flex; gap: 24px; align-items: center; margin: 12px 0; }}
  .img-text-layout .slide-image {{ flex: 0 0 45%; margin: 0; }}
  .img-text-layout .slide-body {{ flex: 1; }}

  .controls {{
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 28px; gap: 12px;
  }}

  .btn {{
    background: {cfg['slide_bg']}; color: {cfg['title_color']};
    border: 1px solid {cfg['accent']}; padding: 10px 28px;
    border-radius: 50px; font-size: .95rem; font-family: inherit;
    cursor: pointer; transition: all .2s;
  }}

  .btn:hover {{ background: {cfg['accent']}; color: #fff; transform: translateY(-1px); }}
  .btn:disabled {{ opacity: .3; cursor: default; transform: none; }}

  .progress {{ flex: 1; height: 4px; background: rgba(255,255,255,.08); border-radius: 4px; overflow: hidden; }}
  .progress-fill {{ height: 100%; background: {cfg['accent']}; border-radius: 4px; transition: width .4s ease; }}

  @media (max-width: 640px) {{
    .slide {{ padding: 32px 24px; min-height: 360px; }}
    .btn {{ padding: 8px 18px; font-size: .85rem; }}
    .img-text-layout {{ flex-direction: column; }}
    .compare-grid {{ grid-template-columns: 1fr; }}
    .stat-cards {{ flex-direction: column; }}
  }}
</style>
</head>
<body>
<div class="deck">
  {slides_html}
  <div class="controls">
    <button class="btn" id="prev" onclick="go(-1)">← Oldingi</button>
    <div class="progress"><div class="progress-fill" id="prog" style="width:{100/total:.1f}%"></div></div>
    <button class="btn" id="next" onclick="go(1)">Keyingi →</button>
  </div>
</div>

<script>
  var cur = 0, total = {total};
  function go(dir) {{
    document.getElementById('s' + cur).style.display = 'none';
    cur = (cur + dir + total) % total;
    document.getElementById('s' + cur).style.display = 'flex';
    document.getElementById('prog').style.width = ((cur + 1) / total * 100) + '%';
    document.getElementById('prev').disabled = cur === 0;
    document.getElementById('next').disabled = cur === total - 1;
  }}
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight' || e.key === ' ') go(1);
    if (e.key === 'ArrowLeft') go(-1);
  }});
  var sx = 0;
  document.addEventListener('touchstart', function(e) {{ sx = e.touches[0].clientX; }});
  document.addEventListener('touchend', function(e) {{
    var dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
  }});
  document.getElementById('prev').disabled = true;
  if (total <= 1) document.getElementById('next').disabled = true;
</script>
</body>
</html>"""

    def _render_slide_html(self, slide: dict, cfg: dict) -> str:
        """Slayd turiga qarab HTML render."""
        stype = slide.get("type", "content")
        title = self._esc(slide.get("title", ""))
        subtitle = self._esc(slide.get("subtitle", ""))
        body = self._esc(slide.get("body", ""))
        emoji = slide.get("emoji", "📌")
        points = slide.get("points", [])
        image_url = slide.get("image_url", "")

        subtitle_html = f'<div class="slide-subtitle">{subtitle}</div>' if subtitle else ""
        body_html = f'<div class="slide-body">{body}</div>' if body else ""
        image_html = f'<div class="slide-image"><img src="{image_url}" alt="" loading="lazy"></div>' if image_url else ""

        points_html = ""
        if points:
            items = "".join(f"<li>{self._esc(p)}</li>" for p in points)
            points_html = f'<ul class="slide-points">{items}</ul>'

        # ── Turiga qarab layout ──
        if stype == "title":
            return f"""
            <div class="slide--title" style="text-align:center;width:100%">
                <div class="slide-emoji" style="font-size:4rem">{emoji}</div>
                <h2 class="slide-title" style="font-size:clamp(2rem,4vw,3rem)">{title}</h2>
                {subtitle_html}
                {image_html}
            </div>"""

        if stype == "quote":
            return f"""
            <div class="slide--quote">
                <div class="slide-emoji">{emoji}</div>
                <div class="slide-body" style="font-size:clamp(1.2rem,2vw,1.6rem);font-style:italic;border-left:4px solid {cfg['accent']};padding-left:24px;margin:20px 0">
                    "{body}"
                </div>
                {subtitle_html}
            </div>"""

        if stype == "chart" and points:
            cards = ""
            for p in points:
                cards += f'<div class="stat-card"><div class="stat-label">{self._esc(p)}</div></div>'
            return f"""
                <div class="slide-emoji">{emoji}</div>
                <h2 class="slide-title">{title}</h2>
                {subtitle_html}
                {body_html}
                <div class="stat-cards">{cards}</div>"""

        if stype == "image_text" and image_url:
            return f"""
                <div class="slide-emoji">{emoji}</div>
                <h2 class="slide-title">{title}</h2>
                {subtitle_html}
                <div class="img-text-layout">
                    <div class="slide-image"><img src="{image_url}" alt="" loading="lazy"></div>
                    <div style="flex:1">
                        {body_html}
                        {points_html}
                    </div>
                </div>"""

        if stype == "comparison" and len(points) >= 2:
            mid = len(points) // 2
            left_items = "".join(f"<li>{self._esc(p)}</li>" for p in points[:mid])
            right_items = "".join(f"<li>{self._esc(p)}</li>" for p in points[mid:])
            return f"""
                <div class="slide-emoji">{emoji}</div>
                <h2 class="slide-title">{title}</h2>
                {subtitle_html}
                {body_html}
                <div class="compare-grid">
                    <div class="compare-col"><ul class="slide-points">{left_items}</ul></div>
                    <div class="compare-col"><ul class="slide-points">{right_items}</ul></div>
                </div>"""

        # ── Default layout (problem, solution, content, team, closing) ──
        return f"""
                <div class="slide-emoji">{emoji}</div>
                <h2 class="slide-title">{title}</h2>
                {subtitle_html}
                {image_html}
                {body_html}
                {points_html}"""

    # ══════════════════════════════════════════════════════════
    # STAGE 5: PPTX BUILDER
    # ══════════════════════════════════════════════════════════

    def _build_pptx(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        try:
            import httpx
            import tempfile
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN

            cfg = theme

            def hex_to_rgb(h: str) -> RGBColor:
                h = h.lstrip("#")
                return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

            prs = Presentation()
            prs.slide_width = Inches(13.33)
            prs.slide_height = Inches(7.5)

            slide_bg_rgb = hex_to_rgb(cfg["slide_bg"])
            title_rgb = hex_to_rgb(cfg["title_color"])
            body_rgb = hex_to_rgb(cfg["body_color"])
            accent_rgb = hex_to_rgb(cfg["accent"])

            for slide_data in slides:
                layout = prs.slide_layouts[6]  # blank
                sl = prs.slides.add_slide(layout)

                # Fon
                bg = sl.background.fill
                bg.solid()
                bg.fore_color.rgb = slide_bg_rgb

                # Accent chiziq (chapdan)
                bar = sl.shapes.add_shape(1, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
                bar.fill.solid()
                bar.fill.fore_color.rgb = accent_rgb
                bar.line.fill.background()

                stype = slide_data.get("type", "content")

                # Emoji
                tx = sl.shapes.add_textbox(Inches(0.5), Inches(0.6), Inches(2), Inches(0.8))
                tf = tx.text_frame
                p = tf.paragraphs[0]
                p.text = slide_data.get("emoji", "📌")
                p.font.size = Pt(32)

                # Title
                title_top = Inches(1.4)
                if stype == "title":
                    # Title slayd — markazda, katta
                    tx = sl.shapes.add_textbox(Inches(1.5), Inches(2.0), Inches(10), Inches(2))
                    tf = tx.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_data.get("title", "")
                    p.font.bold = True
                    p.font.size = Pt(44)
                    p.font.color.rgb = title_rgb
                    p.alignment = PP_ALIGN.CENTER

                    # Subtitle
                    subtitle = slide_data.get("subtitle", "")
                    if subtitle:
                        p2 = tf.add_paragraph()
                        p2.text = subtitle
                        p2.font.size = Pt(24)
                        p2.font.color.rgb = accent_rgb
                        p2.alignment = PP_ALIGN.CENTER
                        p2.space_before = Pt(16)
                else:
                    # Normal title
                    tx = sl.shapes.add_textbox(Inches(0.5), title_top, Inches(12.5), Inches(1.2))
                    tf = tx.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_data.get("title", "")
                    p.font.bold = True
                    p.font.size = Pt(32)
                    p.font.color.rgb = title_rgb

                    # Subtitle
                    subtitle = slide_data.get("subtitle", "")
                    if subtitle:
                        p2 = tf.add_paragraph()
                        p2.text = subtitle
                        p2.font.size = Pt(20)
                        p2.font.color.rgb = accent_rgb
                        p2.space_before = Pt(6)

                # Skip body/points for title slide
                if stype == "title":
                    continue

                # Rasm uchun joy aniqlash
                has_image = bool(slide_data.get("image_url"))
                body_left = Inches(0.5)
                body_width = Inches(12.5)
                body_top = Inches(2.8)

                if has_image:
                    try:
                        img_url = slide_data["image_url"]
                        with httpx.Client(timeout=15.0, follow_redirects=True) as http:
                            resp = http.get(img_url)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                                tmp.write(resp.content)
                                tmp_path = tmp.name
                            if stype == "image_text":
                                sl.shapes.add_picture(tmp_path, Inches(0.5), Inches(2.8), Inches(5.5), Inches(4.0))
                                body_left = Inches(6.5)
                                body_width = Inches(6.5)
                            else:
                                sl.shapes.add_picture(tmp_path, Inches(7.5), Inches(1.5), Inches(5.5), Inches(3.5))
                                body_width = Inches(6.8)
                            os.remove(tmp_path)
                    except Exception as img_err:
                        print(f"[Pipeline] PPTX rasm xatosi: {img_err}")

                # Body matn
                body = slide_data.get("body", "")
                if body:
                    tx = sl.shapes.add_textbox(body_left, body_top, body_width, Inches(2.0))
                    tf = tx.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = body
                    p.font.size = Pt(16)
                    p.font.color.rgb = body_rgb
                    p.line_spacing = Pt(24)

                # Points
                points = slide_data.get("points", [])
                if points:
                    points_top = body_top + Inches(2.2) if body else body_top
                    tx = sl.shapes.add_textbox(body_left, points_top, body_width, Inches(3.0))
                    tf = tx.text_frame
                    tf.word_wrap = True
                    first = True
                    for point in points:
                        p = tf.paragraphs[0] if first else tf.add_paragraph()
                        first = False
                        p.text = f"• {point}"
                        p.font.size = Pt(16)
                        p.font.color.rgb = body_rgb
                        p.space_before = Pt(6)

            prs.save(path)

        except ImportError:
            print("[Pipeline] python-pptx o'rnatilmagan!")
            open(path, "wb").close()
        except Exception as e:
            print(f"[Pipeline] PPTX xatosi: {e}")
            import traceback
            traceback.print_exc()
            open(path, "wb").close()

    # ══════════════════════════════════════════════════════════
    # STAGE 6: PDF (via Playwright)
    # ══════════════════════════════════════════════════════════

    def _build_pdf(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        pass

    async def _build_pdf_async(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        print_html = self._build_print_html(topic, slides, theme)
        tmp_html_path = path.replace(".pdf", "_print.html")

        try:
            with open(tmp_html_path, "w", encoding="utf-8") as f:
                f.write(print_html)

            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"file:///{tmp_html_path.replace(os.sep, '/')}", wait_until="networkidle")
                await page.wait_for_timeout(2000)
                await page.pdf(
                    path=path, format="A4", landscape=True, print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
                )
                await browser.close()
        except Exception as e:
            print(f"[Pipeline] Playwright PDF xatosi: {e}")
            open(path, "wb").close()
        finally:
            if os.path.exists(tmp_html_path):
                os.remove(tmp_html_path)

    def _build_print_html(self, topic: str, slides: list[dict], theme: dict) -> str:
        cfg = theme
        slides_html = ""
        for i, s in enumerate(slides):
            inner = self._render_slide_html(s, cfg)
            slides_html += f"""
        <div class="slide">
            <div class="slide-num">{i+1} / {len(slides)}</div>
            {inner}
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>{self._esc(topic)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@400;600;700&family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@400;700&display=swap');
  @page {{ size: 1920px 1080px; margin: 0; }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: {cfg['font']};
    background: {cfg['page_bg']};
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .slide {{
    background: {cfg['slide_bg']};
    width: 100vw; height: 100vh;
    padding: 80px 120px;
    display: flex; flex-direction: column; justify-content: center;
    position: relative; page-break-after: always;
    border: 10px solid {cfg.get('accent', '#3b82f6')};
  }}

  .slide-num {{
    position: absolute; top: 60px; right: 80px;
    font-size: 2rem; color: {cfg['num_color']};
  }}

  .slide-emoji {{ font-size: 4rem; margin-bottom: 20px; }}
  .slide-title {{ font-size: 4rem; font-weight: 700; color: {cfg['title_color']}; line-height: 1.2; margin-bottom: 30px; }}
  .slide-subtitle {{ font-size: 2.5rem; color: {cfg['accent']}; margin-bottom: 20px; }}
  .slide-body {{ font-size: 2rem; color: {cfg['body_color']}; line-height: 1.8; }}

  .slide-points {{ list-style: none; padding: 0; }}
  .slide-points li {{ padding: 10px 0 10px 40px; position: relative; font-size: 2rem; color: {cfg['body_color']}; }}
  .slide-points li::before {{
    content: ''; position: absolute; left: 0; top: 50%;
    transform: translateY(-50%); width: 16px; height: 16px;
    border-radius: 50%; background: {cfg['accent']};
  }}

  .slide-image {{ margin: 20px 0; border-radius: 16px; overflow: hidden; }}
  .slide-image img {{ width: 100%; max-height: 400px; object-fit: cover; display: block; }}

  .stat-cards {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
  .stat-card {{ flex: 1; min-width: 200px; padding: 30px; border-radius: 16px; background: {cfg['accent']}22; text-align: center; }}
  .stat-card .stat-num {{ font-size: 2.5rem; font-weight: 700; color: {cfg['accent']}; }}
  .stat-card .stat-label {{ font-size: 1.5rem; color: {cfg['body_color']}; }}

  .compare-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 20px 0; }}
  .compare-col {{ padding: 30px; border-radius: 16px; background: {cfg['accent']}11; }}

  .img-text-layout {{ display: flex; gap: 40px; align-items: center; }}
  .img-text-layout .slide-image {{ flex: 0 0 45%; margin: 0; }}
</style>
</head>
<body>
  {slides_html}
</body>
</html>"""

    # ══════════════════════════════════════════════════════════
    # TELEGRAM
    # ══════════════════════════════════════════════════════════

    async def _send_to_telegram(self, telegram_id: int, pptx_path: str, pdf_path: str, topic: str) -> bool:
        try:
            import httpx
            from app.core.config import settings

            api_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
            sent_any = False

            async with httpx.AsyncClient(timeout=60.0) as client:
                # PPTX
                if os.path.exists(pptx_path) and os.path.getsize(pptx_path) > 0:
                    with open(pptx_path, "rb") as fh:
                        resp = await client.post(
                            f"{api_url}/sendDocument",
                            data={
                                "chat_id": str(telegram_id),
                                "caption": f"📊 <b>{topic}</b>\n\n✅ PPTX taqdimotingiz tayyor!",
                                "parse_mode": "HTML",
                            },
                            files={"document": (f"{topic[:40]}.pptx", fh, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                        )
                    if resp.status_code == 200:
                        sent_any = True

                # PDF
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    with open(pdf_path, "rb") as fh:
                        resp = await client.post(
                            f"{api_url}/sendDocument",
                            data={
                                "chat_id": str(telegram_id),
                                "caption": f"📄 <b>{topic}</b>\n\n✅ PDF versiyasi tayyor!",
                                "parse_mode": "HTML",
                            },
                            files={"document": (f"{topic[:40]}.pdf", fh, "application/pdf")},
                        )
                    if resp.status_code == 200:
                        sent_any = True

            return sent_any

        except Exception as e:
            print(f"[Pipeline] Telegram yuborish xatosi: {e}")
            return False

    # ══════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _esc(text: str) -> str:
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    @staticmethod
    def _clean_json(raw: str) -> str:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        start = raw.find("[") if "[" in raw else raw.find("{")
        end = max(raw.rfind("]"), raw.rfind("}")) + 1
        if start != -1 and end > 0:
            raw = raw[start:end]
        return raw
