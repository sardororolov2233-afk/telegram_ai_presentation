"""
Taqdimot Generatsiya Pipeline
Oqim: Groq API → JSON slaydlar → HTML → PPTX + PDF → Telegram
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

GROQ_MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────

class PresentationPipeline:
    """
    Oqim:
      1. Groq API → JSON (slaydlar ro'yxati)
      2. JSON → chiroyli HTML slideshow
      3. HTML → PPTX (python-pptx)
      4. HTML → PDF  (reportlab)
      5. Telegram orqali PPTX yuborish (ixtiyoriy)
    """

    def _output_dir(self) -> str:
        """Fayllar saqlanadigan papkani qaytaradi (cross-platform)."""
        d = os.path.join(os.path.expanduser("~"), "presentations_cache")
        os.makedirs(d, exist_ok=True)
        return d

    # ── Public entry point ─────────────────────────────────────

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

        # 1. Dizayn shablonini tanlash
        theme = DESIGN_TEMPLATES.get(design_template, DESIGN_TEMPLATES[1]).copy()
        print(f"[Pipeline] Shablon: {theme.get('theme_name', '?')}")

        # 2. Groq → slaydlar
        slides = await self._generate_slides(topic, language, slide_count, style, extra_context)

        # 3. HTML yaratish va saqlash
        html = self._build_html(topic, slides, theme)
        with open(f"{out}/{pid}.html", "w", encoding="utf-8") as f:
            f.write(html)

        # 4. PPTX yaratish
        pptx_path = f"{out}/{pid}.pptx"
        self._build_pptx(topic, slides, theme, pptx_path)

        # 5. PDF yaratish
        pdf_path = f"{out}/{pid}.pdf"
        await self._build_pdf_async(topic, slides, theme, pdf_path)


        # 6. Telegram yuborish
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

    # _generate_theme() olib tashlandi — endi DESIGN_TEMPLATES dan tanlangan shablon ishlatiladi

    # ── Step 1: Groq API ───────────────────────────────────────

    async def _generate_slides(
        self,
        topic: str,
        language: str,
        slide_count: int,
        style: str,
        extra_context: Optional[str],
    ) -> list[dict]:
        from app.core.config import settings

        if not settings.GROQ_API_KEY:
            return self._demo_slides(topic, slide_count, language)

        lang_map = {"uz": "O'zbek tilida", "ru": "на русском языке", "en": "in English"}
        lang_str = lang_map.get(language, "in English")
        extra = f"\n\nQo'shimcha kontekst: {extra_context}" if extra_context else ""

        prompt = f"""Sen professional taqdimot (prezentatsiya) yaratuvchi AI yordamchisan.
Quyidagi mavzuda {slide_count} ta slayd yarat. Til: {lang_str}.
Mavzu: {topic}{extra}

MUHIM TALABLAR:
1. HAR BIR slaydning "body" maydoni 50-100 so'zdan iborat akademik, ilmiy uslubdagi matn bo'lsin.
   Matn paragraf ko'rinishida, chuqur ma'noli va mavzuga tegishli bo'lsin.
2. Maksimal 5 ta slaydda "image_query" maydoni bo'lsin — bu Unsplash dan rasm izlash uchun
   ingliz tilidagi 1-3 so'zlik kalit so'z. Qolgan slaydlarda image_query bo'lmasin.
3. Birinchi slayd — kirish (mavzu nomi va akademik tavsif).
4. Oxirgi slayd — xulosa va keyingi qadamlar.

Faqat quyidagi JSON formatda javob ber, boshqa hech narsa yozma:
[
  {{
    "title": "Slayd sarlavhasi",
    "body": "50-100 so'zlik akademik matn. Paragraf ko'rinishida yozing, bullet point emas.",
    "emoji": "🎯",
    "image_query": "keyword",
    "notes": "Notiq uchun qo'shimcha izoh"
  }}
]

Eslatma: image_query ni faqat 5 ta slaydga qo'shing, qolganlarida bo'lmasin."""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            response = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Sen JSON formatda javob beradigan taqdimot yaratuvchi AI yordamchisan. Faqat valid JSON qaytarasan.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=8192,
            )

            raw = response.choices[0].message.content.strip()

            # JSON tozalash
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            # Faqat [ ... ] qismini olish
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end > 0:
                raw = raw[start:end]

            slides = json.loads(raw)

            # Validatsiya: har bir slaydda title va body bo'lishi shart
            validated = []
            for s in slides:
                if isinstance(s, dict) and "title" in s and "body" in s:
                    slide_dict = {
                        "title": str(s.get("title", "")),
                        "body":  str(s.get("body", "")),
                        "emoji": str(s.get("emoji", "📌")),
                        "notes": str(s.get("notes", "")),
                    }
                    if s.get("image_query"):
                        slide_dict["image_query"] = str(s["image_query"])
                    validated.append(slide_dict)

            return validated[:slide_count] if validated else self._demo_slides(topic, slide_count, language)

        except Exception as exc:
            print(f"[Pipeline] Groq xatosi: {exc}")
            return self._demo_slides(topic, slide_count, language)

    def _demo_slides(self, topic: str, count: int, lang: str) -> list[dict]:
        """Groq API yo'q yoki xato bo'lsa — demo slaydlar."""
        titles_uz = ["Kirish", "Asosiy g'oyalar", "Afzalliklari", "Misol va holat", "Xulosa"]
        titles_ru = ["Введение", "Основные идеи", "Преимущества", "Пример", "Заключение"]
        titles_en = ["Introduction", "Key Ideas", "Advantages", "Example", "Conclusion"]
        emojis    = ["🚀", "💡", "✅", "📊", "🎯"]

        titles = titles_uz if lang == "uz" else titles_ru if lang == "ru" else titles_en
        slides = []
        for i in range(count):
            idx = i % len(titles)
            slides.append({
                "title": f"{titles[idx]}: {topic}" if i == 0 else titles[idx % len(titles)],
                "body":  f"{topic} haqida {i+1}-qism ma'lumoti.\n- Muhim nuqta 1\n- Muhim nuqta 2\n- Muhim nuqta 3",
                "emoji": emojis[idx],
                "notes": "",
            })
        return slides

    # ── Step 2: HTML Slideshow ─────────────────────────────────

    def _build_html(self, topic: str, slides: list[dict], theme: dict) -> str:
        cfg = theme
        total = len(slides)

        slides_html = ""
        for i, s in enumerate(slides):
            body_html = self._format_body(s["body"])
            display = "flex" if i == 0 else "none"
            image_html = ""
            if s.get("image_query"):
                q = s["image_query"].replace(" ", ",")
                image_html = f'<div class="slide-image"><img src="https://source.unsplash.com/800x400/?{q}" alt="{self._esc(s["image_query"])}" loading="lazy"></div>'
            slides_html += f"""
        <div class="slide" id="s{i}" style="display:{display}">
            <div class="slide-num">{i+1} / {total}</div>
            <div class="slide-emoji">{s['emoji']}</div>
            <h2 class="slide-title">{self._esc(s['title'])}</h2>
            {image_html}
            <div class="slide-body">{body_html}</div>
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._esc(topic)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@400;600;700&family=DM+Sans:wght@400;500;700&display=swap');

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

  .deck {{
    width: 100%;
    max-width: 960px;
  }}

  .slide {{
    background: {cfg['slide_bg']};
    border-radius: 24px;
    padding: 56px 64px;
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
    position: absolute;
    top: 20px; right: 28px;
    font-size: .8rem;
    color: {cfg['num_color']};
    letter-spacing: .05em;
  }}

  .slide-emoji {{
    font-size: 3.2rem;
    margin-bottom: 18px;
    line-height: 1;
  }}

  .slide-title {{
    font-size: clamp(1.5rem, 3vw, 2.2rem);
    font-weight: 700;
    color: {cfg['title_color']};
    line-height: 1.2;
    margin-bottom: 24px;
  }}

  .slide-body {{
    font-size: clamp(.95rem, 1.5vw, 1.15rem);
    color: {cfg['body_color']};
    line-height: 1.85;
  }}

  .slide-image {{
    margin: 16px 0;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,.25);
  }}

  .slide-image img {{
    width: 100%;
    max-height: 240px;
    object-fit: cover;
    display: block;
  }}

  .slide-body ul {{
    list-style: none;
    padding: 0;
  }}

  .slide-body ul li {{
    padding: 6px 0 6px 22px;
    position: relative;
  }}

  .slide-body ul li::before {{
    content: '';
    position: absolute;
    left: 0; top: 50%;
    transform: translateY(-50%);
    width: 8px; height: 8px;
    border-radius: 50%;
    background: {cfg['accent']};
  }}

  .controls {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 28px;
    gap: 12px;
  }}

  .btn {{
    background: {cfg['slide_bg']};
    color: {cfg['title_color']};
    border: 1px solid {cfg['accent']};
    padding: 10px 28px;
    border-radius: 50px;
    font-size: .95rem;
    font-family: inherit;
    cursor: pointer;
    transition: all .2s;
  }}

  .btn:hover {{ background: {cfg['accent']}; color: #fff; transform: translateY(-1px); }}
  .btn:disabled {{ opacity: .3; cursor: default; transform: none; }}

  .progress {{
    flex: 1;
    height: 4px;
    background: rgba(255,255,255,.08);
    border-radius: 4px;
    overflow: hidden;
  }}

  .progress-fill {{
    height: 100%;
    background: {cfg['accent']};
    border-radius: 4px;
    transition: width .4s ease;
  }}

  @media (max-width: 640px) {{
    .slide {{ padding: 36px 28px; min-height: 360px; }}
    .btn {{ padding: 8px 18px; font-size: .85rem; }}
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
    var el = document.getElementById('s' + cur);
    el.style.display = 'none';
    cur = (cur + dir + total) % total;
    var next = document.getElementById('s' + cur);
    next.style.display = 'flex';
    document.getElementById('prog').style.width = ((cur + 1) / total * 100) + '%';
    document.getElementById('prev').disabled = cur === 0;
    document.getElementById('next').disabled = cur === total - 1;
  }}

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight' || e.key === ' ') go(1);
    if (e.key === 'ArrowLeft')  go(-1);
  }});

  // Swipe support
  var sx = 0;
  document.addEventListener('touchstart', function(e) {{ sx = e.touches[0].clientX; }});
  document.addEventListener('touchend', function(e) {{
    var dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
  }});

  // Init state
  document.getElementById('prev').disabled = true;
  if (total <= 1) document.getElementById('next').disabled = true;
</script>
</body>
</html>"""

    def _format_body(self, body: str) -> str:
        """Matnni HTML ga aylantiradi: - bilan boshlanadigan qatorlar → <ul>"""
        lines = body.split("\n")
        items = [l.strip() for l in lines if l.strip()]
        if not items:
            return ""

        # Bullet point larni ajratish
        bullets = [l[1:].strip() for l in items if l.startswith("-")]
        plain   = [l for l in items if not l.startswith("-")]

        html = ""
        if plain:
            html += "<p>" + "<br>".join(self._esc(p) for p in plain) + "</p>"
        if bullets:
            html += "<ul>" + "".join(f"<li>{self._esc(b)}</li>" for b in bullets) + "</ul>"
        return html

    @staticmethod
    def _esc(text: str) -> str:
        """HTML maxsus belgilarini escape qiladi."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    # ── Step 3: PPTX ──────────────────────────────────────────

    def _build_pptx(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        try:
            import httpx
            import tempfile
            from pptx import Presentation
            from pptx.util import Inches, Pt, Emu
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN

            cfg = theme

            def hex_to_rgb(h: str) -> RGBColor:
                h = h.lstrip("#")
                return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

            prs = Presentation()
            prs.slide_width  = Inches(13.33)
            prs.slide_height = Inches(7.5)

            slide_bg_rgb    = hex_to_rgb(cfg["slide_bg"])
            title_rgb       = hex_to_rgb(cfg["title_color"])
            body_rgb        = hex_to_rgb(cfg["body_color"])
            accent_rgb      = hex_to_rgb(cfg["accent"])

            for slide_data in slides:
                layout = prs.slide_layouts[6]  # blank
                slide  = prs.slides.add_slide(layout)

                # Fon
                bg = slide.background.fill
                bg.solid()
                bg.fore_color.rgb = slide_bg_rgb

                # Accent chiziq (chapdan)
                bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
                bar.fill.solid()
                bar.fill.fore_color.rgb = accent_rgb
                bar.line.fill.background()

                # Emoji
                tx_emoji = slide.shapes.add_textbox(Inches(0.5), Inches(0.8), Inches(2), Inches(1))
                tf = tx_emoji.text_frame
                p  = tf.paragraphs[0]
                p.text = slide_data.get("emoji", "📌")
                p.font.size = Pt(36)

                # Sarlavha
                tx_title = slide.shapes.add_textbox(Inches(0.5), Inches(1.7), Inches(12.5), Inches(1.6))
                tf = tx_title.text_frame
                tf.word_wrap = True
                p  = tf.paragraphs[0]
                p.text = slide_data["title"]
                p.font.bold  = True
                p.font.size  = Pt(32)
                p.font.color.rgb = title_rgb

                # Matn (body)
                has_image = bool(slide_data.get("image_query"))
                body_top = Inches(3.4)
                body_height = Inches(3.6)

                # Rasm qo'shish (agar image_query mavjud bo'lsa)
                if has_image:
                    try:
                        q = slide_data["image_query"].replace(" ", ",")
                        img_url = f"https://source.unsplash.com/800x400/?{q}"
                        with httpx.Client(timeout=15.0, follow_redirects=True) as http:
                            resp = http.get(img_url)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                                tmp.write(resp.content)
                                tmp_path = tmp.name
                            slide.shapes.add_picture(tmp_path, Inches(7.5), Inches(1.5), Inches(5.5), Inches(3.5))
                            os.remove(tmp_path)
                            # Body narrower when image present
                            body_top = Inches(1.7)
                            body_height = Inches(5.3)
                    except Exception as img_err:
                        print(f"[Pipeline] PPTX rasm xatosi: {img_err}")

                tx_body = slide.shapes.add_textbox(Inches(0.5), body_top, Inches(7.0) if has_image else Inches(12.5), body_height)
                tf = tx_body.text_frame
                tf.word_wrap = True

                body_lines = [l.strip() for l in slide_data["body"].split("\n") if l.strip()]
                first = True
                for line in body_lines:
                    p = tf.paragraphs[0] if first else tf.add_paragraph()
                    first = False
                    is_bullet = line.startswith("-")
                    p.text = line[1:].strip() if is_bullet else line
                    p.level = 1 if is_bullet else 0
                    p.font.size = Pt(18)
                    p.font.color.rgb = body_rgb
                    if is_bullet:
                        p.space_before = Pt(4)

                # Speaker notes
                notes = slide_data.get("notes", "")
                if notes:
                    notes_slide = slide.notes_slide
                    notes_slide.notes_text_frame.text = notes

            prs.save(path)

        except ImportError:
            open(path, "wb").close()
        except Exception as e:
            print(f"[Pipeline] PPTX xatosi: {e}")
            open(path, "wb").close()

    # ── Step 4: PDF ───────────────────────────────────────────

    def _build_pdf(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        """PDF generation via Playwright (Sync wait for Async operation)"""
        # Build print-friendly HTML
        print_html = self._build_print_html(topic, slides, theme)
        
        # Async dan Sync ga o'tish (Event loop ichida bo'lsa koroutine orqali shuning uchun _build_pdf ni o'zgartirmaymiz yoki uni ham async qilamiz)
        # pipeline.py dagi run() metodi async, u _build_pdf ni chaqiradi. Ammo _build_pdf() sinxron function qilingan.
        # Playwright bilan ishlash uchun yaxshisi asyncio.run() yoki loop.run_until_complete() ishlatamiz yoki
        # Uni async qilib run() qayta yozamiz. Keling uni async qilamiz.
        pass

    async def _build_pdf_async(self, topic: str, slides: list[dict], theme: dict, path: str) -> None:
        import os
        import tempfile
        from playwright.async_api import async_playwright

        print_html = self._build_print_html(topic, slides, theme)

        # Vaqtinchalik HTML fayl yaratamiz
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as f:
            f.write(print_html)
            tmp_html_path = f.name

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                page = await browser.new_page()
                
                # Faylni yuklaymiz
                await page.goto(f"file://{tmp_html_path}", wait_until="networkidle")
                
                # PDF ga eksport qilamiz
                await page.pdf(
                    path=path,
                    format="A4",
                    landscape=True,
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
                )
                
                await browser.close()
        except Exception as e:
            print(f"[Pipeline] Playwright PDF xatosi: {e}")
            open(path, "wb").close()
        finally:
            # Vaqtinchalik HTML faylni o'chiramiz
            if os.path.exists(tmp_html_path):
                os.remove(tmp_html_path)

    def _build_print_html(self, topic: str, slides: list[dict], theme: dict) -> str:
        cfg = theme
        slides_html = ""
        for i, s in enumerate(slides):
            body_html = self._format_body(s["body"])
            image_html = ""
            if s.get("image_query"):
                q = s["image_query"].replace(" ", ",")
                image_html = f'<div class="slide-image-print"><img src="https://source.unsplash.com/1200x600/?{q}" alt="{self._esc(s["image_query"])}"></div>'
            slides_html += f"""
        <div class="slide">
            <div class="slide-num">{i+1} / {len(slides)}</div>
            <div class="slide-emoji">{s.get('emoji', '📌')}</div>
            <h2 class="slide-title">{self._esc(s['title'])}</h2>
            {image_html}
            <div class="slide-body">{body_html}</div>
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._esc(topic)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@400;600;700&family=DM+Sans:wght@400;500;700&display=swap');
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
    width: 100vw;
    height: 100vh;
    padding: 80px 120px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    page-break-after: always;
    border: 10px solid {cfg.get('accent', '#3b82f6')};
  }}

  .slide-num {{
    position: absolute;
    top: 60px; right: 80px;
    font-size: 2rem;
    color: {cfg['num_color']};
  }}

  .slide-emoji {{
    font-size: 6rem;
    margin-bottom: 20px;
  }}

  .slide-title {{
    font-size: 5rem;
    font-weight: 700;
    color: {cfg['title_color']};
    line-height: 1.2;
    margin-bottom: 40px;
  }}

  .slide-body {{
    font-size: 2.5rem;
    color: {cfg['body_color']};
    line-height: 1.8;
  }}

  .slide-body ul {{
    list-style: none;
    padding: 0;
  }}

  .slide-body ul li {{
    padding: 10px 0 10px 40px;
    position: relative;
  }}

  .slide-body ul li::before {{
    content: '';
    position: absolute;
    left: 0; top: 50%;
    transform: translateY(-50%);
    width: 16px; height: 16px;
    border-radius: 50%;
    background: {cfg['accent']};
  }}

  .slide-image-print {{
    margin: 30px 0;
    border-radius: 16px;
    overflow: hidden;
  }}

  .slide-image-print img {{
    width: 100%;
    max-height: 400px;
    object-fit: cover;
    display: block;
  }}
</style>
</head>
<body>
  {slides_html}
</body>
</html>"""

    # ── Step 5: Telegram ──────────────────────────────────────

    async def _send_to_telegram(self, telegram_id: int, pptx_path: str, pdf_path: str, topic: str) -> bool:
        try:
            import httpx
            from app.core.config import settings

            api_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
            sent_any = False

            async with httpx.AsyncClient(timeout=60.0) as client:
                # PPTX yuborish
                if os.path.exists(pptx_path) and os.path.getsize(pptx_path) > 0:
                    with open(pptx_path, "rb") as fh:
                        resp = await client.post(
                            f"{api_url}/sendDocument",
                            data={
                                "chat_id": str(telegram_id),
                                "caption": f"📊 <b>{topic}</b>\n\n✅ PPTX taqdimotingiz tayyor!",
                                "parse_mode": "HTML",
                            },
                            files={
                                "document": (
                                    f"{topic[:40]}.pptx",
                                    fh,
                                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                )
                            },
                        )
                    if resp.status_code == 200:
                        sent_any = True

                # PDF yuborish
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    with open(pdf_path, "rb") as fh:
                        resp = await client.post(
                            f"{api_url}/sendDocument",
                            data={
                                "chat_id": str(telegram_id),
                                "caption": f"📄 <b>{topic}</b>\n\n✅ PDF versiyasi tayyor!",
                                "parse_mode": "HTML",
                            },
                            files={
                                "document": (
                                    f"{topic[:40]}.pdf",
                                    fh,
                                    "application/pdf",
                                )
                            },
                        )
                    if resp.status_code == 200:
                        sent_any = True

            return sent_any

        except Exception as e:
            print(f"[Pipeline] Telegram yuborish xatosi: {e}")
            return False
