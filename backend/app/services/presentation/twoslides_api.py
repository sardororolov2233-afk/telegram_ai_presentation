import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

async def generate_presentation_from_2slides(
    api_key: str, 
    topic: str, 
    author: str, 
    slide_count: int,
    user_uid: str
) -> str:
    """
    Calls 2slides.com API to generate a presentation and returns the downloadUrl.
    """
    url = "https://2slides.com/api/v1/slides/generate"
    
    # Format the prompt
    prompt_text = f"Topic: {topic}"
    if author:
        prompt_text += f"\nAuthor: {author}"
    if slide_count:
        prompt_text += f"\nPages: {slide_count}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt_text,
        "user_uid": str(user_uid),
        "slide_count": slide_count,
        "mode": "sync"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Navigate standard nested responses if present
            if "downloadUrl" in data:
                return data["downloadUrl"]
            elif "data" in data and "downloadUrl" in data["data"]:
                return data["data"]["downloadUrl"]
            elif "url" in data:
                return data["url"]
            else:
                logger.error(f"2Slides No URL generated. Response: {data}")
                raise Exception("2Slides did not return a valid download link.")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"2Slides HTTP Error {e.response.status_code}: {e.response.text}")
            raise Exception(f"Failed to generate 2slides presentation. Bad request/Error.")
        except httpx.RequestError as e:
            logger.error(f"2Slides Request Error: {e}")
            raise Exception("Cannot connect to 2slides API.")
