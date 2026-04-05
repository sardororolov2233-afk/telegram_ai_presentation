import json
import httpx
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings


@dataclass
class SlideData:
    index: int
    title: str
    content_text: str = ""
    bullets: list = field(default_factory=list)
    slide_type: str = "content"
    image_keyword: str = ""
    raw_data: dict = field(default_factory=dict)


# ============================================================
#  SYSTEM PROMPT — Taqdimot uchun (Mukammal versiya)
# ============================================================
 
SYSTEM_PROMPT = """You are a world-class presentation architect and academic visual content strategist.
Your task is to generate rich, structured, and highly academic slide content.
 
CRITICAL ACADEMIC REQUIREMENT:
- Each slide MUST present a single, complete, and distinct academic concept (yaxlit bitta akademik ahamiyatga ega bo'lishi shart). 
- Do not fragment a single thought across multiple slides.
- Ensure high academic density but maintain visual clarity.

SLIDE TYPE REFERENCE:
- title              → Opening slide: big title + subtitle + tagline
- agenda             → Table of contents
- content            → Text only: title + bullets (3–5 items)
- content_image_right→ LEFT: title + bullets | RIGHT: image in rounded rectangle frame
- content_image_left → LEFT: image in rounded rectangle frame | RIGHT: title + bullets
- table              → Title + data table (headers + rows)
- chart_bar          → Title + bar chart data + ONE insight sentence (NO image, NO long text)
- chart_pie          → Title + pie chart data + ONE insight sentence (NO image, NO long text)
- chart_line         → Title + line chart data + ONE insight sentence (NO image, NO long text)
- quote              → Big quote or key statistic highlight
- section            → Chapter divider: title + subtitle
- conclusion         → Final slide: key takeaways + call to action
 
STRICT RULES:
1. Return ONLY a valid JSON array — no markdown, no explanation, no code fences
2. First slide MUST be type "title", last slide MUST be type "conclusion"
3. MUST include at least 1 image slide (content_image_right or content_image_left)
4. MUST include at least 1 table slide
5. MUST include at least 1 chart slide (bar, pie, or line)
6. chart_bar / chart_pie / chart_line → ONLY: title + chart data + insight. NO bullets, NO image_keyword
7. content_image_right / content_image_left → text and image are side by side, never overlapping
8. image_keyword must always be in English (for image search accuracy)
9. All visible text must be in the requested language
10. content_text: EVERY slide MUST contain a single unified paragraph composed of up to 200 words (yaxlit matn). DO NOT use bullets (unless absolutely necessary for simple lists).
11. Each slide must have a unified, singular academic focus preventing thin or fragmented content.
12. NEVER output `speaker_notes`. Put all informational value directly into `content_text`.
"""
 
 
# ============================================================
#  USER PROMPT — Mukammal, to'liq strukturali
# ============================================================
 
def build_user_prompt(
    topic: str,
    language: str,
    slide_count: int,
    style: str,
    extra_context: Optional[str] = None,
    audience: Optional[str] = None,
    purpose: Optional[str] = None,
) -> str:
 
    lang_map = {
        "uz": "Uzbek — O'zbek tili (lotin yozuvi, rasmiy akademik uslub)",
        "ru": "Russian — Русский язык (официальный академический стиль)",
        "en": "English — formal academic and professional style",
    }
    lang_name     = lang_map.get(language, "English — formal academic and professional style")
    audience_line = f"Target audience: {audience}" if audience else "Target audience: university students / professionals"
    purpose_line  = f"Purpose: {purpose}"          if purpose  else "Purpose: educational / informational presentation"
    extra_line    = f"Additional context: {extra_context}" if extra_context else ""
 
    return f"""Create a {slide_count}-slide presentation about: "{topic}"
 
Language: {lang_name}
Style: {style}
{audience_line}
{purpose_line}
{extra_line}
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLIDE SCHEMAS — use exact field names
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 
▸ TITLE
{{
  "index": 0,
  "slide_type": "title",
  "title": "Main presentation title",
  "subtitle": "Descriptive subtitle",
  "tagline": "One powerful hook sentence",
  "content_text": "A brief opening paragraph to introduce the topic."
}}
 
▸ AGENDA
{{
  "index": 1,
  "slide_type": "agenda",
  "title": "Agenda",
  "content_text": "A unified text listing all the topics.",
  "items": ["Topic 1", "Topic 2", "Topic 3", "Topic 4"]
}}
 
▸ CONTENT (text only)
{{
  "index": 2,
  "slide_type": "content",
  "title": "Slide Title",
  "content_text": "A unified, comprehensive academic paragraph of up to 200 words explaining the core concept in deep detail."
}}
 
▸ CONTENT + IMAGE RIGHT  (text LEFT, image RIGHT — side by side, no overlap)
{{
  "index": 3,
  "slide_type": "content_image_right",
  "title": "Slide Title",
  "content_text": "A comprehensive academic paragraph of up to 200 words analyzing the concept visually represented.",
  "image_keyword": "relevant english keyword for image search"
}}
 
▸ CONTENT + IMAGE LEFT  (image LEFT, text RIGHT — side by side, no overlap)
{{
  "index": 4,
  "slide_type": "content_image_left",
  "title": "Slide Title",
  "content_text": "A comprehensive academic paragraph of up to 200 words explaining the subject alongside the visual.",
  "image_keyword": "relevant english keyword for image search"
}}
 
▸ TABLE
{{
  "index": 5,
  "slide_type": "table",
  "title": "Comparison / Data Table",
  "table": {{
    "headers": ["Column A", "Column B", "Column C", "Column D"],
    "rows": [
      ["Row 1 A", "Row 1 B", "Row 1 C", "Row 1 D"],
      ["Row 2 A", "Row 2 B", "Row 2 C", "Row 2 D"],
      ["Row 3 A", "Row 3 B", "Row 3 C", "Row 3 D"]
    ]
  }},
  "content_text": "A paragraph explaining the findings shown in this data table."
}}
 
▸ BAR CHART  ← ONLY title + chart data + insight (NO bullets, NO image)
{{
  "index": 6,
  "slide_type": "chart_bar",
  "title": "Chart Title",
  "chart": {{
    "x_label": "Category axis label",
    "y_label": "Value axis label",
    "data": [
      {{"label": "Category A", "value": 75}},
      {{"label": "Category B", "value": 42}},
      {{"label": "Category C", "value": 88}},
      {{"label": "Category D", "value": 60}}
    ]
  }},
  "insight": "One key takeaway from this chart.",
  "content_text": "A descriptive paragraph analyzing the chart."
}}
 
▸ PIE CHART  ← ONLY title + chart data + insight (NO bullets, NO image)
{{
  "index": 7,
  "slide_type": "chart_pie",
  "title": "Chart Title",
  "chart": {{
    "data": [
      {{"label": "Segment A", "value": 35}},
      {{"label": "Segment B", "value": 25}},
      {{"label": "Segment C", "value": 20}},
      {{"label": "Segment D", "value": 20}}
    ]
  }},
  "insight": "Key observation about the distribution.",
  "content_text": "A descriptive paragraph analyzing the chart."
}}
 
▸ LINE CHART  ← ONLY title + chart data + insight (NO bullets, NO image)
{{
  "index": 8,
  "slide_type": "chart_line",
  "title": "Trend Over Time",
  "chart": {{
    "x_label": "Time period",
    "y_label": "Value",
    "data": [
      {{"label": "2019", "value": 30}},
      {{"label": "2020", "value": 45}},
      {{"label": "2021", "value": 38}},
      {{"label": "2022", "value": 62}},
      {{"label": "2023", "value": 80}}
    ]
  }},
  "insight": "What this trend tells us.",
  "content_text": "A descriptive paragraph analyzing the overall trend."
}}
 
▸ QUOTE
{{
  "index": 9,
  "slide_type": "quote",
  "title": "Key Insight",
  "quote": "A powerful statement or key statistic",
  "author": "Source or author (if applicable)",
  "content_text": "A descriptive paragraph explaining why this quote is fundamentally important."
}}
 
▸ SECTION DIVIDER
{{
  "index": 10,
  "slide_type": "section",
  "title": "Section Title",
  "subtitle": "Brief description of this section",
  "content_text": "A short introductory text for the upcoming section."
}}
 
▸ CONCLUSION
{{
  "index": 11,
  "slide_type": "conclusion",
  "title": "Conclusion",
  "key_takeaways": [
    "Most important takeaway 1",
    "Most important takeaway 2",
    "Most important takeaway 3"
  ],
  "call_to_action": "What the audience should do or think next",
  "content_text": "A final summary paragraph closing the presentation powerfully."
}}
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLIDE DISTRIBUTION for {slide_count} slides:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Slide 1       → title
Slide 2       → agenda
Slides 3–{slide_count - 1} → mix of: content, content_image_right, content_image_left,
                table, chart_bar / chart_pie / chart_line, quote, section
                MUST include: ≥1 image slide, ≥1 table slide, ≥1 chart slide
Slide {slide_count}   → conclusion
 
IMPORTANT:
- Chart values must be realistic numbers relevant to "{topic}"
- Table data must be factually reasonable for "{topic}"
- image_keyword describes the visual clearly in English
 
Return ONLY the JSON array. Exactly {slide_count} slides. No extra text.
"""

class AIContentGenerator:
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self):
        self.api_key = getattr(settings, "GROQ_API_KEY", None)
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY .env faylida topilmadi. "
                "Uni qo'shing: GROQ_API_KEY=gsk_..."
            )

    async def generate_slides(
        self,
        topic: str,
        language: str = "uz",
        slide_count: int = 8,
        style: str = "professional",
        extra_context: Optional[str] = None,
    ) -> list[SlideData]:
        prompt = build_user_prompt(topic, language, slide_count, style, extra_context)

        payload = {
            "model": self.MODEL,
            "max_tokens": 4096,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.GROQ_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        raw_text = data["choices"][0]["message"]["content"].strip()

        # Markdown kod blokini tozalash: ```json ... ``` yoki ``` ... ```
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            # Birinchi va oxirgi ``` qatorlarini olib tashlaymiz
            inner_lines = lines[1:] if lines else lines
            if inner_lines and inner_lines[-1].strip() == "```":
                inner_lines = inner_lines[:-1]
            raw_text = "\n".join(inner_lines).strip()

        slides_json = json.loads(raw_text)

        slides = []
        for s in slides_json:
            slide_type = s.get("slide_type", "content")
            
            # Matn (bullets o'rnida)
            bullets = []
            
            # 200 ta so'zgacha bo'lgan yagona yaxlit matn qo'shish
            content_text = s.get("content_text", "")
            if content_text:
                bullets.append(content_text)

            # Qo'shimcha (fallback yoki schema elementlari)
            if slide_type == "title":
                if "subtitle" in s: bullets.append(str(s["subtitle"]))
                if "tagline" in s: bullets.append(str(s["tagline"]))
            elif slide_type == "agenda":
                if "items" in s and isinstance(s["items"], list):
                    bullets.extend(str(item) for item in s["items"])
            elif slide_type in ["chart_bar", "chart_pie", "chart_line"]:
                if "insight" in s: bullets.append(f"Insight: {s['insight']}")
            elif slide_type == "table":
                pass # Table o'zi table rendering funksiyasida ishlanadi, unga bullets qo'shib chalkashtirmaymiz, content_text yetarli
            elif slide_type == "quote":
                if "quote" in s: bullets.append(f'"{s["quote"]}"')
                if "author" in s: bullets.append(f"— {s['author']}")
            elif slide_type == "conclusion":
                if "key_takeaways" in s and isinstance(s["key_takeaways"], list):
                    bullets.extend(str(k) for k in s["key_takeaways"])
                if "call_to_action" in s: bullets.append(str(s["call_to_action"]))

            # Eskicha bullets json dan bo'lsa uni qo'shib yuborish
            legacy_bullets = s.get("bullets", [])
            if isinstance(legacy_bullets, list):
                bullets.extend(legacy_bullets)

            slides.append(SlideData(
                index=s.get("index", 0),
                title=s.get("title", ""),
                bullets=bullets,  # Endi bullets list asosan 1 ta paragraph content_text va boshqa kerakli pointlar bilan band
                slide_type=slide_type,
                image_keyword=s.get("image_keyword", "") if s.get("image_keyword") else "",
                raw_data=s
            ))
        return slides
