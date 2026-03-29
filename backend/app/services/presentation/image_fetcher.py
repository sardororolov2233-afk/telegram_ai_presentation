"""
Image Fetcher — Pollinations.ai orqali rasmlar olish (Bepul, kalit talab qilinmaydi)
"""
import httpx
import os
import uuid
import urllib.parse
from typing import Optional

PRESENTATIONS_DIR = "/tmp/presentations"
IMAGES_DIR = f"{PRESENTATIONS_DIR}/images"


def cleanup_images(image_paths: list) -> None:
    """PPTX ga qo'shilgandan keyin vaqtinchalik rasmlarni o'chiradi."""
    for path in image_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[ImageFetcher] O'chirishda xato: {e}")


async def fetch_image_for_topic(query: str, index: int = 0) -> Optional[str]:
    """Pollinations.ai dan rasm yuklab olish (Bepul, no API key)."""
    if not query:
        return None
        
    os.makedirs(IMAGES_DIR, exist_ok=True)

    safe_query = urllib.parse.quote(query)
    # Using pollinations to ensure no API key limits + add unique seed for variation
    url = f"https://image.pollinations.ai/prompt/{safe_query}?width=800&height=600&nologo=true&seed={index}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True, headers=headers)
            if resp.status_code != 200:
                print(f"[ImageFetcher] Pollinations xatosi {resp.status_code}, zaxira rasm olinadi")
                # Fallback to Picsum
                resp = await client.get(f"https://picsum.photos/seed/{uuid.uuid4().hex}/800/600", follow_redirects=True, headers=headers)
                if resp.status_code != 200:
                    return None

            img_path = os.path.join(IMAGES_DIR, f"{uuid.uuid4().hex}.jpg")
            with open(img_path, "wb") as f:
                f.write(resp.content)

            return img_path

    except Exception as e:
        print(f"[ImageFetcher] Xato: {e}")
        return None


async def fetch_images_for_slides(keywords: list) -> list:
    """
    Har bir slayd uchun maxsus keyword asosida rasm oladi.
    """
    import asyncio

    # Bir vaqtning o'zida pollinations ni juda ko'p yuklamaslik uchun semafor (ko'pi bilan 3 ta)
    sem = asyncio.Semaphore(3)

    async def _fetch_with_sem(q, idx):
        async with sem:
            # ozgina kutish (rate-limit ni chetlab o'tish uchun)
            await asyncio.sleep(idx * 0.2)
            return await fetch_image_for_topic(q, idx)

    tasks = [_fetch_with_sem(q, idx) for idx, q in enumerate(keywords)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for r in results:
        if isinstance(r, str) and r:
            images.append(r)
        else:
            images.append(None)

    print(f"[ImageFetcher] {sum(1 for i in images if i)} ta rasm olindi. Qidiruvlar: {len(keywords)}")
    return images