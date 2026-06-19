"""
Image Generator — OpenRouter orqali FLUX.2 Klein 4B modelidan rasmlar yaratish.
Narx: ~$0.014/megapixel (birinchi), $0.001 (keyingi) — juda tejamkor.
Fallback: Pollinations.ai (bepul).
"""
import httpx
import os
import uuid
import re
import base64
import urllib.parse
from typing import Optional

from app.core.config import settings

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
FLUX_MODEL = "black-forest-labs/flux.2-pro"

# Rasmlar saqlanadigan papka
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static"))
os.makedirs(STATIC_DIR, exist_ok=True)


def _get_dimensions(format: str) -> tuple[int, int]:
    """Banner formatiga qarab o'lchamlarni aniqlash."""
    dimensions = {
        "instagram": (1024, 1024),   # 1:1
        "telegram":  (1024, 768),    # 4:3
        "story":     (576, 1024),    # 9:16
    }
    return dimensions.get(format, (1024, 1024))


async def generate_image_with_flux(
    prompt: str,
    format: str,
    variant_index: int = 0,
) -> Optional[str]:
    """
    FLUX.2 Klein 4B modelidan rasm yaratish.
    Muvaffaqiyatli bo'lsa — fayl nomi (filename) qaytaradi.
    Xato bo'lsa — None qaytaradi.
    """
    width, height = _get_dimensions(format)
    api_key = settings.OPENROUTER_API_KEY
    
    if not api_key:
        print("[ImageGen] OpenRouter API kaliti topilmadi!")
        return None

    # Har bir variant uchun prompt ni biroz o'zgartiramiz — noyob natijalar uchun
    variant_modifiers = [
        "",  # Original prompt — o'zgarishsiz
        ", different camera angle, alternative color palette and layout",
        ", different composition layout, unique visual arrangement",
    ]
    modifier = variant_modifiers[variant_index % len(variant_modifiers)]
    full_prompt = f"{prompt}{modifier}"

    try:
        payload = {
            "model": FLUX_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt,
                }
            ],
            "modalities": ["image"],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://orzu-two.vercel.app",
            "X-Title": "Yordamchi AI Design Generator",
        }

        async with httpx.AsyncClient(timeout=90) as client:
            print(f"[ImageGen] FLUX so'rov yuborilmoqda (variant #{variant_index + 1})...")
            resp = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"].get("content", "")
            
            # Rasmni ajratib olish (bir necha format bo'lishi mumkin)
            filename = f"design_{uuid.uuid4().hex}.png"
            filepath = os.path.join(STATIC_DIR, filename)

            # 1: Markdown link qidirish: ![alt](url)
            img_match = re.search(r"!\[.*?\]\((.*?)\)", content)
            if img_match:
                img_url = img_match.group(1)
                if img_url.startswith("data:image"):
                    # Base64 inline data
                    b64_data = img_url.split(",", 1)[1]
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    print(f"[ImageGen] ✅ Variant #{variant_index + 1} saqlandi (base64 inline)")
                    return filename
                else:
                    # URL orqali yuklab olish
                    img_resp = await client.get(img_url, timeout=30)
                    if img_resp.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(img_resp.content)
                        print(f"[ImageGen] ✅ Variant #{variant_index + 1} saqlandi (URL)")
                        return filename

            # 2: data:image/...;base64 qidirish
            b64_match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
            if b64_match:
                b64_data = b64_match.group(1)
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                print(f"[ImageGen] ✅ Variant #{variant_index + 1} saqlandi (data URI)")
                return filename

            # 3: Xom JPEG/PNG base64 (ba'zan shunday qaytaradi)
            if len(content) > 200 and " " not in content[:200]:
                try:
                    raw_bytes = base64.b64decode(content)
                    # JPEG yoki PNG ekanligini tekshirish
                    if raw_bytes[:2] == b'\xff\xd8' or raw_bytes[:4] == b'\x89PNG':
                        with open(filepath, "wb") as f:
                            f.write(raw_bytes)
                        print(f"[ImageGen] ✅ Variant #{variant_index + 1} saqlandi (raw base64)")
                        return filename
                except Exception:
                    pass

            print(f"[ImageGen] ⚠️ FLUX javobida rasm topilmadi. Javob: {content[:200]}...")
            return None

    except httpx.HTTPStatusError as e:
        print(f"[ImageGen] ❌ FLUX API xatosi ({e.response.status_code}): {e.response.text[:300]}")
        return None
    except Exception as e:
        print(f"[ImageGen] ❌ FLUX xatosi: {e}")
        return None


async def generate_image_fallback(
    prompt: str,
    format: str,
    variant_index: int = 0,
) -> Optional[str]:
    """
    Pollinations.ai orqali bepul rasm yaratish (fallback).
    """
    width, height = _get_dimensions(format)
    
    safe_query = urllib.parse.quote(prompt[:500])  # URL uzunligi cheklov
    seed = variant_index * 1000 + 42  # Deterministic seed har bir variant uchun
    url = f"https://image.pollinations.ai/prompt/{safe_query}?width={width}&height={height}&nologo=true&seed={seed}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # 2 marta urinish
            for attempt in range(2):
                resp = await client.get(url, follow_redirects=True, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    filename = f"design_{uuid.uuid4().hex}.jpg"
                    filepath = os.path.join(STATIC_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    print(f"[ImageGen] ✅ Fallback variant #{variant_index + 1} saqlandi (Pollinations)")
                    return filename
                    
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2)
            
            # Sub-fallback: Picsum (tematik bo'lmasa ham rasm bor)
            picsum_url = f"https://picsum.photos/{width}/{height}"
            resp = await client.get(picsum_url, follow_redirects=True, headers=headers)
            if resp.status_code == 200:
                filename = f"design_{uuid.uuid4().hex}.jpg"
                filepath = os.path.join(STATIC_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                print(f"[ImageGen] ✅ Fallback variant #{variant_index + 1} saqlandi (Picsum)")
                return filename

    except Exception as e:
        print(f"[ImageGen] ❌ Fallback xatosi: {e}")
    
    return None
