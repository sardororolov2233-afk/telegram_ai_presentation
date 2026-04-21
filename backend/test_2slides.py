import asyncio
import httpx

async def test_api():
    base_url = "https://2slides.com/api/v1/slides/generate"
    headers = {
        "Authorization": "Bearer sk-2slides-851674b50a0b01971ae8b4879b4a51e03ea5c87e48b2d31a286f6ad59833f0ec",
        "Content-Type": "application/json"
    }
    
    data = {
        "userInput": "Quick test presentation", 
        "mode": "sync"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(base_url, headers=headers, json=data)
        print("Status", res.status_code)
        try:
            print("Response:", res.json())
        except:
            print("Text:", res.text)

asyncio.run(test_api())
