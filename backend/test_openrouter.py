import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

# .env faylini o'qiymiz
load_dotenv(".env")
load_dotenv("../.env")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Siz tanlagan model nomi
MODEL = "deepseek/deepseek-r1t2-chimera:free"

async def test_openrouter():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ XATOLIK: OPENROUTER_API_KEY topilmadi! .env faylni tekshiring.")
        return

    print("🔑 API Kalit topildi:", api_key[:12] + "..........." + api_key[-4:])
    print(f"🤖 Model tekshirilmoqda: {MODEL}")
    
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://acadai.uz",
        "X-Title": "AcadAI Presentation Generator",
    }
    
    payload = {
        "model": MODEL,
        "max_tokens": 50,
        "messages": [
            {"role": "user", "content": "Salom! Bu API test aloqasi. Menga faqat 'ALOQA YAXSHI' deb qisqa javob qaytar."}
        ]
    }
    
    print("\n⏳ So'rov yuborilmoqda, kuting...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                OPENROUTER_API_URL,
                json=payload,
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print("\n✅ MUVAFFAQIYAT: API To'g'ri ishlamoqda!")
                print(f"📄 Model javobi: \n{content}")
            else:
                print(f"\n❌ XATOLIK! HTTP Status qodi: {response.status_code}")
                print(f"🔍 To'liq sabab: \n{response.text}")
                
                # Agar 404 xato chiqsa model noto'g'riligi yoki bunday model bepul emasligini tekshiramiz
                if response.status_code == 404:
                    print("\n💡 YECHIM: OpenRouter saytida bu model nomini topib bo'lmadi.")
                    print("Iltimos, model nomini 'deepseek/deepseek-r1:free' ga o'zgartirib ko'ring.")
                    
        except Exception as e:
            print(f"\n❌ TARMOQ xatosi yuz berdi: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
