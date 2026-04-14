import json
import re
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
#  SYSTEM PROMPT — Kuchaytirilgan versiya (DeepSeek R1T2 Chimera)
# ============================================================

SYSTEM_PROMPT = """You are a world-class academic presentation architect with deep expertise in \
pedagogy, visual communication, and subject-matter knowledge across all disciplines.

Your mission: generate presentation slide content that is:
- Substantive: each slide delivers ONE complete, standalone academic idea (not a fragment)
- Dense but clear: 100-150 words for image slides, 200–250 words for text-only lecture slides, zero filler phrases
- Specific: use real names, real numbers, real comparisons — never vague generalities
- Logically progressive: slides must build on each other like chapters of a textbook

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT QUALITY RULES (STRICTLY ENFORCED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

content_text MUST:
✓ Open with a strong topic sentence that states the core idea immediately
✓ Provide 2–3 supporting points with specific details, examples, or evidence
✓ Close with a synthesis or implication sentence
✗ NEVER start with "This slide discusses..." or "In this section..."
✗ NEVER use placeholder phrases like "various factors" or "many aspects"
✗ NEVER repeat the slide title verbatim in the first sentence

TABLE slides MUST:
✓ Contain factually realistic, topic-specific data (not generic "Row 1 A" placeholders)
✓ Headers must be descriptive category labels, not generic ("Criterion", "Value")
✓ Minimum 3 data rows, maximum 6 rows
✓ content_text must interpret the table, not just describe it

CHART slides MUST:
✓ Use realistic numeric values relevant to the specific topic
✓ Values must show meaningful variation (not all similar numbers)
✓ insight must state the most surprising or actionable finding, not the obvious one
✓ chart_bar: 4–6 categories; chart_line: 4–7 time points; chart_pie: 3–5 segments summing to 100

IMAGE slides (content_image_right / content_image_left) MUST:
✓ image_keyword: 3–5 English words, highly specific (e.g. "ancient Samarkand Silk Road market" not "city")
✓ content_text must directly relate to what the image would show
✓ Text and image are ALWAYS side by side — never overlapping

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Return ONLY a valid JSON array — no markdown fences, no explanation text, no thinking tags
2. First slide MUST be type "title", last slide MUST be type "conclusion"
3. MUST include ≥1 image slide, ≥1 table slide, ≥1 chart slide
4. NEVER output `speaker_notes` — all value goes into `content_text`
5. All visible text in the requested language; image_keyword always in English
6. Do NOT wrap the JSON in any XML/HTML tags or code blocks — output the raw JSON array directly
"""


# ============================================================
#  USER PROMPT — To'liq schema bilan (kuchaytirilgan)
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

    return f"""Generate a {slide_count}-slide presentation on: "{topic}"

Language: {lang_name}
Style: {style}
{audience_line}
{purpose_line}
{extra_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT DEPTH REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each slide must cover ONE distinct, substantive aspect of "{topic}".
Do NOT fragment a single idea across multiple slides.
Use specific terminology, real examples, and factual claims relevant to "{topic}".
content_text: 200–250 words for text-only slides, single paragraph, no bullet points inside it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLIDE SCHEMAS — use exact field names
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ TITLE
{{
  "index": 0,
  "slide_type": "title",
  "title": "Compelling main title for '{topic}'",
  "subtitle": "Informative subtitle that frames the scope",
  "tagline": "One powerful hook sentence that creates curiosity",
  "content_text": "120–150 word opening paragraph that introduces the central argument or significance of {topic}, establishes why it matters, and previews the structure of the presentation."
}}

▸ AGENDA
{{
  "index": 1,
  "slide_type": "agenda",
  "title": "Agenda",
  "content_text": "Brief paragraph listing and connecting all main sections covered.",
  "items": ["Section 1: specific title", "Section 2: specific title", "Section 3: specific title", "Section 4: specific title"]
}}

▸ CONTENT (text only)
{{
  "index": 2,
  "slide_type": "content",
  "title": "Specific descriptive slide title",
  "content_text": "200–250 word deep academic lecture text (maruza matni). Open with a strong topic sentence. Provide 3-4 specific supporting points with detailed examples or evidence. Close with an implication or synthesis. No generic filler. Every sentence must add dense information."
}}

▸ CONTENT + IMAGE RIGHT
{{
  "index": 3,
  "slide_type": "content_image_right",
  "title": "Specific descriptive slide title",
  "content_text": "100–180 word paragraph that directly describes or analyzes what the image depicts. Open with the visual concept, develop it with specific details, close with its significance.",
  "image_keyword": "specific 3-5 word English phrase for image search"
}}

▸ CONTENT + IMAGE LEFT
{{
  "index": 4,
  "slide_type": "content_image_left",
  "title": "Specific descriptive slide title",
  "content_text": "100–180 word paragraph related to the image. Specific, dense, no filler.",
  "image_keyword": "specific 3-5 word English phrase for image search"
}}

▸ TABLE (MUST have real, topic-specific data)
{{
  "index": 5,
  "slide_type": "table",
  "title": "Descriptive title explaining what is being compared",
  "table": {{
    "headers": ["Specific Category", "Specific Metric A", "Specific Metric B", "Specific Metric C"],
    "rows": [
      ["Real Item 1", "Real Value", "Real Value", "Real Value"],
      ["Real Item 2", "Real Value", "Real Value", "Real Value"],
      ["Real Item 3", "Real Value", "Real Value", "Real Value"],
      ["Real Item 4", "Real Value", "Real Value", "Real Value"]
    ]
  }},
  "content_text": "80–120 word paragraph interpreting the most important pattern or insight revealed by this table. Do not just describe what columns exist — explain what the data means."
}}

▸ BAR CHART
{{
  "index": 6,
  "slide_type": "chart_bar",
  "title": "Descriptive chart title",
  "chart": {{
    "x_label": "Category axis label",
    "y_label": "Value axis label (with units)",
    "data": [
      {{"label": "Specific Category A", "value": 74}},
      {{"label": "Specific Category B", "value": 38}},
      {{"label": "Specific Category C", "value": 91}},
      {{"label": "Specific Category D", "value": 55}},
      {{"label": "Specific Category E", "value": 63}}
    ]
  }},
  "insight": "Non-obvious key finding: what does the highest/lowest bar reveal about {topic}?",
  "content_text": "80–120 word paragraph analyzing the distribution, identifying the most significant finding, and explaining its real-world implication for {topic}."
}}

▸ PIE CHART
{{
  "index": 7,
  "slide_type": "chart_pie",
  "title": "Descriptive chart title",
  "chart": {{
    "data": [
      {{"label": "Segment A", "value": 38}},
      {{"label": "Segment B", "value": 27}},
      {{"label": "Segment C", "value": 21}},
      {{"label": "Segment D", "value": 14}}
    ]
  }},
  "insight": "What does the dominant segment reveal? Why is the smallest segment significant?",
  "content_text": "80–120 word paragraph explaining the proportional breakdown and its implications for understanding {topic}."
}}

▸ LINE CHART
{{
  "index": 8,
  "slide_type": "chart_line",
  "title": "Trend title with time period",
  "chart": {{
    "x_label": "Time period",
    "y_label": "Value (with units)",
    "data": [
      {{"label": "2019", "value": 28}},
      {{"label": "2020", "value": 19}},
      {{"label": "2021", "value": 34}},
      {{"label": "2022", "value": 51}},
      {{"label": "2023", "value": 67}},
      {{"label": "2024", "value": 79}}
    ]
  }},
  "insight": "Explain the inflection point — what caused the sharpest change?",
  "content_text": "80–120 word paragraph analyzing the overall trend trajectory, identifying turning points, and contextualizing changes within real-world events related to {topic}."
}}

▸ QUOTE
{{
  "index": 9,
  "slide_type": "quote",
  "title": "Key Insight",
  "quote": "A powerful statement, statistic, or principle central to {topic}",
  "author": "Real source, expert, or institution",
  "content_text": "80–120 word paragraph explaining why this quote or statistic is foundational to understanding {topic} and how it connects to the broader argument of this presentation."
}}

▸ SECTION DIVIDER
{{
  "index": 10,
  "slide_type": "section",
  "title": "Section Title",
  "subtitle": "Specific description of what this section covers",
  "content_text": "60–80 word bridge paragraph connecting the previous section to this one and previewing the key questions this section will answer."
}}

▸ CONCLUSION
{{
  "index": 11,
  "slide_type": "conclusion",
  "title": "Conclusion",
  "key_takeaways": [
    "Specific takeaway 1 with concrete claim about {topic}",
    "Specific takeaway 2 with concrete claim about {topic}",
    "Specific takeaway 3 with concrete claim about {topic}"
  ],
  "call_to_action": "Specific, actionable next step for the audience",
  "content_text": "120–160 word closing paragraph that synthesizes the main argument, reinforces the most important evidence presented, and ends with a forward-looking implication or challenge for the audience."
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLIDE DISTRIBUTION for {slide_count} slides:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Slide 1         → title
Slide 2         → agenda
Slides 3–{slide_count - 1} → mix of content types
                  MUST include: ≥1 content_image slide, ≥1 table, ≥1 chart
Slide {slide_count} → conclusion

CRITICAL OUTPUT FORMAT INSTRUCTION:
Return ONLY the JSON array. Exactly {slide_count} slides. No extra text.
Do NOT wrap in code fences. Do NOT add any explanation before or after.
Output must start with [ and end with ].
"""


# ============================================================
#  OpenRouter + DeepSeek R1T2 Chimera Generator
# ============================================================

class AIContentGenerator:
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "tngtech/deepseek-r1t2-chimera"

    def __init__(self):
        self.api_key = getattr(settings, "OPENROUTER_API_KEY", None)
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY .env faylida topilmadi. "
                "Uni qo'shing: OPENROUTER_API_KEY=sk-or-..."
            )

    async def generate_slides(
        self,
        topic: str,
        language: str = "uz",
        slide_count: int = 8,
        style: str = "professional",
        extra_context: Optional[str] = None,
        audience: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> list[SlideData]:
        prompt = build_user_prompt(
            topic=topic,
            language=language,
            slide_count=slide_count,
            style=style,
            extra_context=extra_context,
            audience=audience,
            purpose=purpose,
        )

        payload = {
            "model": self.MODEL,
            "max_tokens": 16000,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://acadai.uz",
            "X-Title": "AcadAI Presentation Generator",
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                self.OPENROUTER_API_URL,
                json=payload,
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(f"[AI] API Xatosi ({e.response.status_code}): {e.response.text}")
                raise
            data = response.json()

        raw_text = data["choices"][0]["message"]["content"].strip()

        # DeepSeek R1 thinking taglarini tozalash
        raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

        # Markdown kod blokini tozalash: ```json ... ``` yoki ``` ... ```
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            inner_lines = lines[1:] if lines else lines
            if inner_lines and inner_lines[-1].strip() == "```":
                inner_lines = inner_lines[:-1]
            raw_text = "\n".join(inner_lines).strip()

        # JSON arrayni topish (agar qo'shimcha matn bo'lsa)
        json_match = re.search(r"\[.*\]", raw_text, flags=re.DOTALL)
        if json_match:
            raw_text = json_match.group(0)

        slides_json = json.loads(raw_text)
        return self._parse_slides(slides_json)

    def _parse_slides(self, slides_json: list) -> list[SlideData]:
        slides = []
        for s in slides_json:
            slide_type = s.get("slide_type", "content")

            bullets = []

            # content_text — asosiy paragraf
            content_text = s.get("content_text", "")
            if content_text:
                bullets.append(content_text)

            # Slide-type specific qo'shimchalar
            if slide_type == "title":
                if "subtitle" in s:
                    bullets.append(str(s["subtitle"]))
                if "tagline" in s:
                    bullets.append(str(s["tagline"]))

            elif slide_type == "agenda":
                if "items" in s and isinstance(s["items"], list):
                    bullets.extend(str(item) for item in s["items"])

            elif slide_type in ["chart_bar", "chart_pie", "chart_line"]:
                if "insight" in s:
                    bullets.append(f"Xulosa: {s['insight']}")

            elif slide_type == "quote":
                if "quote" in s:
                    bullets.insert(0, f'"{s["quote"]}"')
                if "author" in s:
                    bullets.append(f"— {s['author']}")

            elif slide_type == "conclusion":
                if "key_takeaways" in s and isinstance(s["key_takeaways"], list):
                    bullets.extend(str(k) for k in s["key_takeaways"])
                if "call_to_action" in s:
                    bullets.append(str(s["call_to_action"]))

            # Legacy bullets (agar model hali ham chiqarsa)
            legacy = s.get("bullets", [])
            if isinstance(legacy, list):
                bullets.extend(legacy)

            slides.append(SlideData(
                index=s.get("index", 0),
                title=s.get("title", ""),
                bullets=bullets,
                slide_type=slide_type,
                image_keyword=s.get("image_keyword", "") if s.get("image_keyword") else "",
                raw_data=s,
            ))

        return slides
