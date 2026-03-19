"""
AI Content Generator
====================
Claude API orqali taqdimot mazmunini generatsiya qiladi.
Qaytaradi: List[SlideData] — har bir slide uchun sarlavha + mazmun
"""

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
    slide_type: str = "content"  # "title" | "content" | "section" | "conclusion"


SYSTEM_PROMPT = """You are an expert presentation designer and content strategist.
Generate slide content that is:
- Clear, concise, and impactful
- Well-structured with logical flow
- Professional yet engaging
- Appropriate for the requested language

ALWAYS respond with valid JSON only. No markdown, no explanation."""


def build_user_prompt(
    topic: str,
    language: str,
    slide_count: int,
    style: str,
    extra_context: Optional[str],
) -> str:
    lang_map = {"uz": "Uzbek", "ru": "Russian", "en": "English"}
    lang_name = lang_map.get(language, "English")

    return f"""Create a {slide_count}-slide presentation about: "{topic}"
Language: {lang_name}
Style: {style}
{"Additional context: " + extra_context if extra_context else ""}

Return ONLY a JSON array like this:
[
  {{
    "index": 0,
    "slide_type": "title",
    "title": "Main Title",
    "bullets": ["Subtitle or tagline"],
    "speaker_notes": "Opening remarks..."
  }},
  {{
    "index": 1,
    "slide_type": "content",
    "title": "Slide Title",
    "bullets": ["Point 1", "Point 2", "Point 3"],
    "speaker_notes": "What to say here..."
  }}
]

Rules:
- First slide: type="title"
- Last slide: type="conclusion"  
- Middle slides: type="content" or type="section" for chapter dividers
- 3-5 bullets per content slide (short, punchy)
- Total slides: exactly {slide_count}
"""


class AIContentGenerator:
    """Claude API orqali taqdimot mazmuni generatsiya qiladi."""

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-opus-4-6"

    def __init__(self):
        self.api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY .env faylida topilmadi. "
                "Uni qo'shing: ANTHROPIC_API_KEY=sk-ant-..."
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
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.ANTHROPIC_API_URL, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        raw_text = data["content"][0]["text"].strip()

        # JSON ni tozalash (ba'zan ```json ... ``` bilan o'ralgan bo'ladi)
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

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
