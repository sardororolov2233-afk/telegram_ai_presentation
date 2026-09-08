import base64
import os
import uuid
import httpx
import asyncio
import re
from app.core.config import settings
from app.services.presentation.image_fetcher import fetch_image_for_topic, IMAGES_DIR

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
FLUX_MODEL = "black-forest-labs/flux.2-pro"

async def fetch_pro_images_with_flux(keywords: list) -> list:
    """
    Groq orqali slayd matni uchun inglizcha prompt yaratadi va
    OpenRouter API yordamida FLUX.2 Pro modeli orqali rasmlar yaratadi.
    Agar xato bersa, standart image fetcher'ga fallback qiladi.
    """
    groq_api_key = settings.GROQ_API_KEY
    or_api_key = settings.OPENROUTER_API_KEY
    
    if not groq_api_key or not or_api_key:
        print("[ImageFetcher] Groq yoki OpenRouter API kaliti yo'q. Standart usulga o'tilmoqda.")
        tasks = [fetch_image_for_topic(q, i) for i, q in enumerate(keywords)]
        return await asyncio.gather(*tasks)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    sem = asyncio.Semaphore(2)

    async def _fetch(q, idx):
        async with sem:
            await asyncio.sleep(idx * 2) # rate limitdan qochish
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    # 1. Groq orqali prompt yaratish
                    groq_payload = {
                        "model": GROQ_MODEL,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert prompt engineer. You will receive a text or keyword from a presentation slide. Your task is to write a highly detailed, professional, high-resolution English prompt for FLUX.2 Pro to generate a suitable illustration/photograph for this slide. Do not include any text in the image. Output ONLY the prompt text, no explanations."
                            },
                            {
                                "role": "user",
                                "content": str(q)
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 250,
                    }
                    
                    groq_resp = await client.post(
                        GROQ_API_URL, 
                        json=groq_payload, 
                        headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"}
                    )
                    groq_resp.raise_for_status()
                    english_prompt = groq_resp.json()["choices"][0]["message"]["content"].strip()
                    print(f"[ImageFetcher] Groq prompt ({idx}): {english_prompt[:100]}...")

                    # 2. FLUX.2 Pro orqali rasm yaratish
                    flux_payload = {
                        "model": FLUX_MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": english_prompt
                            }
                        ],
                        "modalities": ["image"],
                    }
                    
                    flux_headers = {
                        "Authorization": f"Bearer {or_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://orzu-two.vercel.app",
                        "X-Title": "Yordamchi AI Presentation Generator",
                    }
                    
                    flux_resp = await client.post(
                        OPENROUTER_API_URL, 
                        json=flux_payload, 
                        headers=flux_headers
                    )
                    flux_resp.raise_for_status()
                    data = flux_resp.json()
                    message = data["choices"][0]["message"]
                    
                    filename = f"pro_{uuid.uuid4().hex}.jpg"
                    img_path = os.path.join(IMAGES_DIR, filename)

                    # Rasmni olish strategiyasi
                    if "images" in message and message["images"]:
                        img_url = message["images"][0].get("image_url", {}).get("url", "")
                        if img_url.startswith("data:image"):
                            b64_data = img_url.split(",", 1)[1]
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            return img_path
                        elif img_url:
                            img_resp = await client.get(img_url, timeout=30)
                            if img_resp.status_code == 200:
                                with open(img_path, "wb") as f:
                                    f.write(img_resp.content)
                                return img_path

                    content = message.get("content", "") or ""

                    img_match = re.search(r"!\[.*?\]\((.*?)\)", content)
                    if img_match:
                        img_url = img_match.group(1)
                        if img_url.startswith("data:image"):
                            b64_data = img_url.split(",", 1)[1]
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            return img_path
                        else:
                            img_resp = await client.get(img_url, timeout=30)
                            if img_resp.status_code == 200:
                                with open(img_path, "wb") as f:
                                    f.write(img_resp.content)
                                return img_path

                    b64_match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
                    if b64_match:
                        b64_data = b64_match.group(1)
                        with open(img_path, "wb") as f:
                            f.write(base64.b64decode(b64_data))
                        return img_path

                    if len(content) > 200 and " " not in content[:200]:
                        try:
                            raw_bytes = base64.b64decode(content)
                            if raw_bytes[:2] == b'\xff\xd8' or raw_bytes[:4] == b'\x89PNG':
                                with open(img_path, "wb") as f:
                                    f.write(raw_bytes)
                                return img_path
                        except Exception:
                            pass

                    raise ValueError("FLUX rasm qaytarmadi: " + content[:50])

            except Exception as e:
                print(f"[ImageFetcher] FLUX/Groq Xatosi ({str(q)[:30]}): {e}. Fallback ishlatilmoqda.")
                return await fetch_image_for_topic(q, idx)

    tasks = [_fetch(q, idx) for idx, q in enumerate(keywords)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for r in results:
        if isinstance(r, str) and r:
            images.append(r)
        else:
            images.append(None)
    
    print(f"[ImageFetcher] PRO rejim (FLUX): {sum(1 for i in images if i)} ta rasm olindi.")
    return images
