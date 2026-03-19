"""
Image Fetcher — Unsplash API orqali rasmlar olish
"""
import httpx
import os
import uuid
from typing import Optional
from app.core.config import settings

PRESENTATIONS_DIR = "/tmp/presentations"
IMAGES_DIR = f"{PRESENTATIONS_DIR}/images"


async def fetch_image_for_topic(query: str) -> Optional[str]:
    """Unsplash dan bitta rasm yuklab, yo'lini qaytaradi."""
    if not settings.UNSPLASH_ACCESS_KEY:
        print("[ImageFetcher] UNSPLASH_ACCESS_KEY yo'q, rasm o'tkazib yuborildi")
        return None

    os.makedirs(IMAGES_DIR, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Rasm qidirish
            resp = await client.get(
                "https://api.unsplash.com/photos/random",
                params={
                    "query": query,
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            img_url = data.get("urls", {}).get("regular")
            if not img_url:
                return None

            # Rasmni yuklab olish
            img_resp = await client.get(img_url)
            if img_resp.status_code != 200:
                return None

            img_path = os.path.join(IMAGES_DIR, f"{uuid.uuid4().hex}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_resp.content)

            return img_path

    except Exception as e:
        print(f"[ImageFetcher] Xato: {e}")
        return None


async def fetch_images_for_slides(topic: str, slide_count: int) -> list:
    """
    Har bir slayd uchun Unsplash dan rasm oladi.
    Maksimum 3 ta unikal rasm olib, keyin takrorlaydi.
    """
    import asyncio

    # 3 ta unikal rasm yetarli (takrorlanadi)
    fetch_count = min(3, slide_count)
    queries = [topic] * fetch_count

    tasks = [fetch_image_for_topic(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = [r for r in results if isinstance(r, str) and r]
    print(f"[ImageFetcher] {len(images)} ta rasm olindi")
    return images