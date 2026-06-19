"""
Prompt Enhancer — Groq (Llama 3) yordamida foydalanuvchi promptini
FLUX uchun professional darajada optimallashtiradi.

MUHIM: Foydalanuvchi yozgan barcha matnlarni (o'zbek tilida) 
AYNAN SHU HOLATDA saqlaydi va FLUX ga uzatadi.
Bepul API — qo'shimcha xarajat yo'q.
"""
import httpx
from app.core.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an expert graphic design prompt engineer for AI image generation (FLUX Pro model which CAN render text accurately).

Your task: Take the user's design description and create an optimized English prompt for FLUX image generation.

STEP 1 — CLASSIFY the user's words into two categories:

CATEGORY A — "INSTRUCTIONS" (do NOT put on image, use as visual guidance):
  These are requests/commands about how the design should look.
  Examples: "menga yasab ber", "ranglar qizil bo'lsin", "chiroyli qilib", "fon qora bo'lsin", "rasmni katta qil", "reklamasi", "banner kerak", "professional bo'lsin"
  → Convert these into English visual descriptions (colors, style, composition)

CATEGORY B — "AD TEXT" (MUST appear on the image exactly as written):
  These are slogans, prices, discounts, product names, phone numbers, addresses, brand names.
  Examples: "15% chegirma", "35 000 so'm", "JUMA AKSIYASI", "+998 90 123 45 67", "GRAND LAVASH", "Bepul yetkazib berish"
  → Preserve EXACTLY in original language. You MUST wrap each text EXACTLY in this format:
  text reading "YOUR EXACT TEXT"
  Do not use any other phrasing for text (no "written as", no "with the words"). ONLY use: text reading "..."

STEP 2 — BUILD the prompt:
1. First describe the VISUAL scene in English (from Category A + your design knowledge)
2. Then specify each Category B text with placement, size, font, and color

EXAMPLES:

User: "menga lavash reklamasi yasab ber, juma aksiyasi 15% chegirma, narxi 35000 so'm, fon qora rangda bo'lsin"
Analysis: "menga yasab ber" = instruction, "lavash reklamasi" = instruction (make lavash ad), "fon qora rangda" = instruction → dark background, "juma aksiyasi" = ad text, "15% chegirma" = ad text, "narxi 35000 so'm" = ad text
Prompt: "Professional food advertisement, appetizing golden lavash flatbread with steam, dark black elegant background, warm studio lighting, top-down angle. Large bold text reading "JUMA AKSIYASI" at top in white impact font. Bright yellow text reading "-15% CHEGIRMA" in bold. Text reading "35 000 so'm" in white elegant font at bottom. Commercial food photography, 8K."

User: "IT akademiya uchun chiroyli reklama, kurslar boshlanadi, narxi arzon, zamonaviy dizayn bo'lsin"
Analysis: "uchun chiroyli reklama" = instruction, "zamonaviy dizayn bo'lsin" = instruction, "kurslar boshlanadi" = ad text, "narxi arzon" = ad text
Prompt: "Modern futuristic IT academy advertisement, sleek dark blue and neon purple background, floating code snippets and holographic laptop, glowing circuit patterns. Bold text reading "KURSLAR BOSHLANADI" in glowing cyan sans-serif. Text reading "NARXI ARZON" in white bold font. Ultra modern tech aesthetic, high resolution."

OUTPUT RULES:
- Output ONLY the prompt, no explanations
- Visual parts in English, ad text in original language
- 80-150 words
- Include quality boosters: "professional", "high resolution", "8K"
- Start directly with the description"""


async def enhance_prompt(description: str, format: str, style: str, lang: str = "uz") -> str:
    """
    Foydalanuvchining tavsifini FLUX uchun optimallashtirilgan promptga aylantiradi.
    Barcha matnlar tanlangan tilda saqlanadi yoki o'sha tilga moslashtiriladi.
    """
    
    lang_mapping = {
        "uz": "Uzbek language",
        "kaa": "Karakalpak language",
        "ru": "Russian language",
        "en": "English language"
    }
    target_lang_desc = lang_mapping.get(lang, "Uzbek language")
    
    format_context = {
        "instagram": "square Instagram post (1:1 aspect ratio, 1024x1024)",
        "telegram": "landscape Telegram banner (4:3 aspect ratio, 1024x768)",
        "story": "vertical Story/Reels (9:16 aspect ratio, 576x1024)",
    }
    
    style_context = {
        "infographic": "modern infographic style — clean layout, bold color blocks, structured sections, professional icons",
        "photorealistic": "photorealistic style — studio photography lighting, realistic textures, cinematic depth, commercial aesthetic",
        "3d": "3D illustration style — volumetric objects, neon gradients, glossy surfaces, floating elements, ambient glow",
        "minimalism": "minimalist style — clean whitespace, elegant composition, muted palette, refined geometry",
    }
    
    fmt_desc = format_context.get(format, format_context["instagram"])
    sty_desc = style_context.get(style, style_context["infographic"])
    
    user_message = f"""Create a FLUX image generation prompt for this design request.

USER'S REQUEST: {description}

FORMAT: {fmt_desc}
STYLE: {sty_desc}
TARGET LANGUAGE FOR ALL TEXTS: {target_lang_desc}

IMPORTANT: Keep ALL Category B ad text elements in the target language ({target_lang_desc}). If the user wrote texts in another language but requested {target_lang_desc}, translate the slogan/discount text to {target_lang_desc} but preserve prices/numbers. 
CRITICAL: You MUST wrap each text element strictly in: text reading "EXACT TEXT".
Generate the prompt now."""

    api_key = settings.GROQ_API_KEY
    if not api_key:
        print("[PromptEnhancer] Groq API kaliti topilmadi. Oddiy prompt ishlatilmoqda.")
        return _fallback_prompt(description, format, style, lang)
    
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
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            enhanced = data["choices"][0]["message"]["content"].strip()
            
            # Tozalash
            if enhanced.startswith('"') and enhanced.endswith('"'):
                enhanced = enhanced[1:-1]
            if enhanced.startswith("```"):
                lines = enhanced.split("\n")
                enhanced = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            print(f"[PromptEnhancer] ✅ Prompt optimallashtirildi ({len(enhanced)} belgi)")
            print(f"[PromptEnhancer] 📝 Natija: {enhanced[:200]}...")
            return enhanced
            
    except Exception as e:
        print(f"[PromptEnhancer] ❌ Groq xatosi: {e}. Fallback prompt ishlatilmoqda.")
        return _fallback_prompt(description, format, style, lang)


def _fallback_prompt(description: str, format: str, style: str, lang: str = "uz") -> str:
    """Groq ishlamasa, oddiy prompt yaratish — matnlar saqlanadi."""
    style_words = {
        "infographic": "modern infographic with clean layout",
        "photorealistic": "photorealistic commercial photography with studio lighting",
        "3d": "vibrant 3D illustration with glossy surfaces and neon accents",
        "minimalism": "minimalist design with elegant composition",
    }
    sw = style_words.get(style, "professional design")
    return f'Professional advertisement banner, {sw}, {description}, language: {lang}, ultra high resolution, sharp details, commercial quality, {format} format'
