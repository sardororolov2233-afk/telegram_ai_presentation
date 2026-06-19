import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

async def test_flux2_pro():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    prompt = "Test image generation with text: hello world"
    payload = {
        "model": "black-forest-labs/flux.2-pro",
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "modalities": ["image"],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://orzu-two.vercel.app",
        "X-Title": "Yordamchi AI",
    }
    
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        print("Status code:", resp.status_code)
        try:
            print("Response JSON:", resp.json())
        except Exception as e:
            print("Response text:", resp.text)

if __name__ == "__main__":
    asyncio.run(test_flux2_pro())
