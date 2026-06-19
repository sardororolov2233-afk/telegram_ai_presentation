"""
Prompt Enhancer — Groq (Llama 3) yordamida foydalanuvchi promptini
ingliz tiliga tarjima qiladi va FLUX uchun professional darajada optimallashtiradi.
Bepul API — qo'shimcha xarajat yo'q.
"""
import httpx
from app.core.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an elite graphic design prompt engineer specializing in creating prompts for AI image generation (FLUX model). 

Your task: Take the user's design description (in ANY language — Uzbek, Russian, English, etc.) and transform it into a masterful English prompt optimized for FLUX image generation.

CRITICAL RULES:
1. OUTPUT ONLY THE ENHANCED PROMPT — no explanations, no introductions, no markdown
2. Always write in English
3. Include specific visual details: exact colors (e.g. "deep indigo #4F46E5"), lighting type, composition
4. Specify typography style if text is needed: "bold modern sans-serif", "elegant serif"
5. If the user mentions TEXT that should appear ON the design, preserve it EXACTLY in its original language and wrap in quotes. Example: text reading "DASTURLASH KURSLARI"
6. Describe layout structure: "centered composition", "left-aligned text with right visual"
7. Include mood/atmosphere: "corporate professional", "vibrant energetic", "sleek futuristic"
8. Add quality boosters: "ultra high resolution", "sharp details", "professional commercial design"
9. Mention what the design is FOR: "social media banner", "advertisement poster", "promotional flyer"
10. Keep between 80-180 words — detailed but focused
11. NEVER include negative prompts or what to avoid
12. Start directly with the design description"""


async def enhance_prompt(description: str, format: str, style: str) -> str:
    """
    Foydalanuvchining o'zbek/rus tilidagi tavsifini FLUX uchun
    ingliz tilida optimallashtirilgan professional promptga aylantiradi.
    """
    
    # Format va uslub uchun kontekst
    format_context = {
        "instagram": "square Instagram post (1:1 aspect ratio), social media optimized",
        "telegram": "landscape Telegram channel banner (4:3 aspect ratio), messaging platform optimized",
        "story": "vertical mobile Story/Reels format (9:16 aspect ratio), full-screen mobile experience",
    }
    
    style_context = {
        "infographic": "modern infographic style — clean data visualization, structured grid layout, bold iconography, professional color-coded sections, sleek flat design elements",
        "photorealistic": "photorealistic style — natural studio lighting, realistic textures and materials, cinematic depth of field, commercial photography aesthetic",
        "3d": "3D illustration style — volumetric rendered objects, isometric perspective, vibrant neon gradients, glossy surfaces, dynamic floating elements with ambient glow",
        "minimalism": "minimalist style — generous whitespace, refined typography hierarchy, muted elegant color palette, clean geometric shapes, sophisticated restraint",
    }
    
    fmt_desc = format_context.get(format, format_context["instagram"])
    sty_desc = style_context.get(style, style_context["infographic"])
    
    user_message = f"""Transform this design request into an optimized FLUX image generation prompt:

USER'S REQUEST: {description}

DESIGN FORMAT: {fmt_desc}
DESIGN STYLE: {sty_desc}

Create the perfect prompt now."""

    api_key = settings.GROQ_API_KEY
    if not api_key:
        print("[PromptEnhancer] Groq API kaliti topilmadi. Oddiy prompt ishlatilmoqda.")
        return _fallback_prompt(description, format, style)
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.75,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            enhanced = data["choices"][0]["message"]["content"].strip()
            
            # Tozalash — ba'zan model qo'shimcha belgilar qo'shadi
            if enhanced.startswith('"') and enhanced.endswith('"'):
                enhanced = enhanced[1:-1]
            if enhanced.startswith("```"):
                lines = enhanced.split("\n")
                enhanced = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            print(f"[PromptEnhancer] ✅ Prompt optimallashtirildi ({len(enhanced)} belgi)")
            return enhanced
            
    except Exception as e:
        print(f"[PromptEnhancer] ❌ Groq xatosi: {e}. Fallback prompt ishlatilmoqda.")
        return _fallback_prompt(description, format, style)


def _fallback_prompt(description: str, format: str, style: str) -> str:
    """Groq ishlamasa, oddiy inglizcha prompt yaratish."""
    style_words = {
        "infographic": "modern infographic with bold typography and clean layout",
        "photorealistic": "photorealistic commercial photography with studio lighting",
        "3d": "vibrant 3D illustration with glossy surfaces and neon accents",
        "minimalism": "minimalist design with elegant typography and whitespace",
    }
    sw = style_words.get(style, "professional design")
    return f"Professional graphic design banner, {sw}, about: {description}, ultra high resolution, sharp details, commercial quality, {format} format"
