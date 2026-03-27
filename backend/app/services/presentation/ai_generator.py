import json
import httpx
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


@dataclass
class SlideData:
    index: int
    title: str
    bullets: list[str]
    speaker_notes: str = ""
    slide_type: str = "content"


# ============================================================
#  SYSTEM PROMPT — Taqdimot uchun (Mukammal versiya)
# ============================================================
 
SYSTEM_PROMPT = """You are a world-class presentation architect and visual content strategist.
Your task is to generate rich, structured slide content with advanced visual elements.
 
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
10. speaker_notes must be 2–4 full sentences
11. Bullets: 3–5 items per content slide, each bullet max 10 words
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
  "speaker_notes": "Full opening remarks."
}}
 
▸ AGENDA
{{
  "index": 1,
  "slide_type": "agenda",
  "title": "Agenda",
  "items": ["Topic 1", "Topic 2", "Topic 3", "Topic 4"],
  "speaker_notes": "Brief walkthrough of what will be covered."
}}
 
▸ CONTENT (text only)
{{
  "index": 2,
  "slide_type": "content",
  "title": "Slide Title",
  "bullets": ["Point one", "Point two", "Point three"],
  "speaker_notes": "Explain each bullet in spoken language."
}}
 
▸ CONTENT + IMAGE RIGHT  (text LEFT, image RIGHT — side by side, no overlap)
{{
  "index": 3,
  "slide_type": "content_image_right",
  "title": "Slide Title",
  "bullets": ["Key insight one", "Key insight two", "Key insight three"],
  "image_keyword": "relevant english keyword for image search",
  "image_caption": "Short caption for the image",
  "speaker_notes": "Describe the image and connect it to the content."
}}
 
▸ CONTENT + IMAGE LEFT  (image LEFT, text RIGHT — side by side, no overlap)
{{
  "index": 4,
  "slide_type": "content_image_left",
  "title": "Slide Title",
  "bullets": ["Key insight one", "Key insight two", "Key insight three"],
  "image_keyword": "relevant english keyword for image search",
  "image_caption": "Short caption",
  "speaker_notes": "Describe the visual element and its relevance."
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
  "speaker_notes": "Explain what the table shows and highlight key comparisons."
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
  "speaker_notes": "Walk through the data and explain the most important trend."
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
  "speaker_notes": "Explain what each segment represents and why the distribution matters."
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
  "speaker_notes": "Describe the trend and its implications."
}}
 
▸ QUOTE
{{
  "index": 9,
  "slide_type": "quote",
  "title": "Key Insight",
  "quote": "A powerful statement or key statistic",
  "author": "Source or author (if applicable)",
  "speaker_notes": "Explain why this quote or fact is significant."
}}
 
▸ SECTION DIVIDER
{{
  "index": 10,
  "slide_type": "section",
  "title": "Section Title",
  "subtitle": "Brief description of this section",
  "speaker_notes": "Transition statement to this new section."
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
  "speaker_notes": "Powerful closing statement."
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

        return [
            SlideData(
                index=s["index"],
                title=s["title"],
                bullets=s.get("bullets", []),
                speaker_notes=s.get("speaker_notes", ""),
                slide_type=s.get("slide_type", "content"),
            )
            for s in slides_json
        ]
