import base64
import json
import re

async def fetch_pro_images_with_gemini(keywords: list) -> list:
    """
    OpenRouter API yordamida google/gemini-2.5-flash-image modeli orqali rasmlar yaratadi.
    Agar xato bersa, Pollinations'ga fallback qiladi.
    """
    import asyncio
    import os
    import uuid
    import httpx
    from app.core.config import settings
    # image_fetcher ga qaramlikdan saqlanish
    from app.services.presentation.image_fetcher import fetch_image_for_topic, IMAGES_DIR

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        print("[ImageFetcher] OpenRouter API kaliti yo'q. Standart usulga o'tilmoqda.")
        # fallback
        tasks = [fetch_image_for_topic(q, i) for i, q in enumerate(keywords)]
        return await asyncio.gather(*tasks)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    sem = asyncio.Semaphore(2)

    async def _fetch(q, idx):
        async with sem:
            await asyncio.sleep(idx * 2) # rate limitdan qochish
            try:
                payload = {
                    "model": "google/gemini-2.5-flash", 
                    # Eslatma: Gemini 2.5 Flash yopilgan bo'lishi mumkinligi uchun prompt maxsus qilingan. 
                    # "google/gemini-2.5-flash" rasm generatori emas, lekin multimodal. 
                    # Openrouter'ning rasm modeli esa misol uchun openai/dall-e-3. Lekin user qat'iy Google talab qilgan.
                    # Aslida model: google/gemini-2.5-flash ni beramiz, lekin o'zi tekst chiqaradi odatda.
                    # Qidiruv malumotiga kora model nomi: google/gemini-2.5-flash-image.
                    "messages": [{"role": "user", "content": f"Generate a highly detailed, professional, high-resolution photograph for a presentation slide about: {q}. ONLY output the image or image markdown. Do not describe it."}],
                }
                
                payload["model"] = "google/gemini-2.5-flash-image"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content", "")
                    
                    # 1: Markdown link qidirish ![alt](url)
                    img_match = re.search(r"!\[.*?\]\((.*?)\)", content)
                    if img_match:
                        img_url = img_match.group(1)
                        if img_url.startswith("data:image"):
                            # Base64 inline
                            b64_data = img_url.split(",")[1]
                            img_path = os.path.join(IMAGES_DIR, f"pro_{uuid.uuid4().hex}.jpg")
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            return img_path
                        else:
                            # Standard URL download
                            img_resp = await client.get(img_url)
                            img_path = os.path.join(IMAGES_DIR, f"pro_{uuid.uuid4().hex}.jpg")
                            with open(img_path, "wb") as f:
                                f.write(img_resp.content)
                            return img_path
                            
                    # 2: Xom base64 qaytargan bo'lsa
                    b64_match = re.search(r"data:image/.*?;base64,([A-Za-z0-9+/=]+)", content)
                    if not b64_match:
                        # Quruq base64 bo'lishi ham mumkin
                        if len(content) > 100 and not " " in content[:100] and content.startswith("/9j/"): # JPEG sarlavhasi
                            b64_data = content
                        else:
                            # Hech qanday rasm topilmadi. Fallback qilinadi
                            raise ValueError("Gemini rasm qaytarmadi: " + content[:50])
                    else:
                        b64_data = b64_match.group(1)
                        
                    img_path = os.path.join(IMAGES_DIR, f"pro_{uuid.uuid4().hex}.jpg")
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    return img_path
            except Exception as e:
                print(f"[ImageFetcher] Gemini Xatosi ({q}): {e}. Fallback ishlatilmoqda.")
                return await fetch_image_for_topic(q, idx)

    tasks = [_fetch(q, idx) for idx, q in enumerate(keywords)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for r in results:
        if isinstance(r, str) and r:
            images.append(r)
        else:
            images.append(None)
    
    print(f"[ImageFetcher] PRO rejim: {sum(1 for i in images if i)} ta rasm olindi.")
    return images
