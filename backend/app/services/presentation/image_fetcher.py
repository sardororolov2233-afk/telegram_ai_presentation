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


async def fetch_image_for_topic(query: str) -> Optional[str]:
    """Pollinations.ai dan rasm yuklab olish (Bepul, no API key)."""
    if not query:
        return None
        
    os.makedirs(IMAGES_DIR, exist_ok=True)

    safe_query = urllib.parse.quote(query)
    # Using pollinations to ensure no API key limits
    url = f"https://image.pollinations.ai/prompt/{safe_query}?width=800&height=600&nologo=true"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True)
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

    tasks = [fetch_image_for_topic(q) for q in keywords]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for r in results:
        if isinstance(r, str) and r:
            images.append(r)
        else:
            images.append(None)

    print(f"[ImageFetcher] {sum(1 for i in images if i)} ta rasm olindi")
    return images