import json
import asyncio
import os
import subprocess
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.services.presentation.telegram_sender import send_status_message, send_document

class ArticlePipeline:
    def __init__(self):
        self.model = "deepseek/deepseek-r1"
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                }
                headers = {
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://orzu-two.vercel.app",
                    "X-Title": "Yordamchi AI Presentation Generator",
                }
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[ArticlePipeline] OpenRouter LLM Error: {e}")
            raise e

    def _extract_json(self, text: str) -> Dict[str, Any]:
        import re
        try:
            # DeepSeek <think> teglarini olib tashlash
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            # Yana boshqa tozalashlar
            text = re.sub(r'[\x00-\x1f\x7f]', '', text)
            
            # Try to extract JSON from markdown blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            # Qo'shimcha tozalash
            text = text.strip()
            if text.startswith('`') or text.endswith('`'):
                text = text.strip('`')
            
            return json.loads(text)
        except Exception as e:
            print(f"[ArticlePipeline] JSON parse xatosi: {e}")
            print(f"Olingan matn: {text}")
            return {}

    async def run(self, topic: str, author: str, language: str, telegram_id: Optional[int]):
        print(f"[{topic}] Maqola generatsiyasi boshlandi...")

        # CHAIN 1: Tuzilma
        c1_sys = "Sen O'zbekiston ilmiy jurnallariga (VAK, SCOPUS, Web of Science) mos maqola tuzilmasini yaratuvchi mutaxassissen. FAQAT JSON formatda javob ber, hech qanday izoh yoki markdown yo'q."
        c1_usr = f'Mavzu: "{topic}"\nFan: "Umumiy"\nJournal: "Oliy ta\'lim jurnali"\nSahifa soni: 8\n\nQuyidagi JSON ni to\'ldir (author qismiga "{author}" ni qoy)'
        
        if telegram_id:
            await send_status_message(telegram_id, "⚙️ 1/6: Maqola ilmiy tuzilmasi shakllantirilmoqda (Chain 1)")
        
        res1 = await self._call_llm(c1_sys, c1_usr)
        chain1_output = self._extract_json(res1)
        
        # CHAIN 2: Kontent
        if telegram_id:
            await send_status_message(telegram_id, "✍️ 2/6: Maqola bo'limlari yozilmoqda (Chain 2)")
        
        chain2_outputs = []
        global_fn = 1
        for sec in chain1_output.get("structure", []):
            if sec.get("type") in ["intro", "chapter", "conclusion"]:
                c2_sys = "Sen ilmiy maqola bo'limlari yozuvchissen. Matn O'zbek ilmiy uslubida, aniq, ixcham bo'lsin. FAQAT JSON formatda javob ber."
                c2_usr = f'Maqola mavzusi: "{topic}"\nBo\'lim: "{sec.get("title", "Bo\'lim")}"\nGlobal footnote boshlash raqami: {global_fn}'
                res2 = await self._call_llm(c2_sys, c2_usr)
                c2_json = self._extract_json(res2)
                chain2_outputs.append(c2_json)
                global_fn = c2_json.get("next_fn_number", global_fn + 2)

        # CHAIN 3: Adabiyotlar ro'yxati
        if telegram_id:
            await send_status_message(telegram_id, "📚 3/6: Adabiyotlar ro'yxati generatsiyasi (Chain 3)")
        
        c3_sys = "Sen O'zbekiston ilmiy maqolalari uchun adabiyotlar ro'yxatini yaratuvchi mutaxassissen. FAQAT JSON formatda javob ber."
        c3_usr = f'Mavzu: "{topic}"\nKerakli soni: 10 ta'
        res3 = await self._call_llm(c3_sys, c3_usr)
        chain3_output = self._extract_json(res3)

        # CHAIN 4: Footnote Resolver
        if telegram_id:
            await send_status_message(telegram_id, "🔗 4/6: Iqtiboslar va Footnotelar ulanmoqda (Chain 4)")
        
        c4_sys = "Sen footnote ID larni tartib raqamlar va to'liq citation matnlarga bog'lovchi tizimsen. FAQAT JSON formatda javob ber."
        c4_usr = f'Kontent mapping: {json.dumps(chain2_outputs)}\nManbalar: {json.dumps(chain3_output)}'
        res4 = await self._call_llm(c4_sys, c4_usr)
        chain4_output = self._extract_json(res4)

        # CHAIN 5: Maxsus maqola bloklari (Annotatsiya + Meta)
        if telegram_id:
            await send_status_message(telegram_id, "📝 5/6: Annotatsiya va UDK kodlari olinmoqda (Chain 5)")
        
        c5_sys = "Sen ilmiy maqola annotatsiyasi va meta bloklar yozuvchissen. FAQAT JSON formatda javob ber."
        c5_usr = f'Mavzu: "{topic}"\nBob nomlari: {[s.get("title") for s in chain1_output.get("structure", [])]}\nXulosa qismi: ...'
        res5 = await self._call_llm(c5_sys, c5_usr)
        chain5_output = self._extract_json(res5)

        # CHAIN 6: Node.js DOCX kodi
        if telegram_id:
            await send_status_message(telegram_id, "🤖 6/6: Node.js DOCX skripti generatsiya qilinmoqda (Chain 6)")
        
        c6_sys = "Sen Node.js docx kutubxonasida O'zbek ilmiy maqolalari yaratuvchi dasturchi sen. FAQAT ishlaydigan JavaScript kodi ber. Hech qanday izoh yo'q."
        c6_usr = f'''Quyidagi to'liq ma'lumotlar asosida Node.js skript yoz:
TUZILMA: {json.dumps(chain1_output)}
KONTENT: {json.dumps(chain2_outputs)}
FOOTNOTE MAP: {json.dumps(chain4_output)}
META: {json.dumps(chain5_output)}

Texnik talablar:
1. A4 format, Times New Roman 14pt, 1.5 interval
2. Muqova: UDK | Sarlavha (3 tilda) | Muallif | Annotatsiya (3 tilda) | Kalit so'zlar
3. Footnote texnologiyasi: docx npm paketi yordamida.
4. Adabiyotlar sahifasi — GOST formatda.
5. Packer.toBuffer(doc).then(buf => fs.writeFileSync('/tmp/maqola.docx', buf))
Yodda tut: fayl nomi "/tmp/maqola.docx" bolishi shart. FAQAT JS kod!'''

        res6 = await self._call_llm(c6_sys, c6_usr)
        
        js_code = res6.replace("```javascript", "").replace("```js", "").replace("```", "").strip()

        if telegram_id:
            await send_status_message(telegram_id, "📦 Skript tayyorlandi. DOCX hujjat yig'ilmoqda...")

        # Fayl yo'llari
        js_file_path = f"/tmp/generate_article_{telegram_id}.js"
        docx_file_path = "/tmp/maqola.docx"

        # Eski maqolani o'chirish (agar bo'lsa)
        if os.path.exists(docx_file_path):
            os.remove(docx_file_path)

        # JS faylni saqlash
        with open(js_file_path, "w", encoding="utf-8") as f:
            f.write(js_code)
        
        # Node ni ishga tushirish (bu jarayonni serverda Node.js o'rnatilganligiga ishonch hosil qilgach ishlatiladi)
        try:
            # Faqat Node o'rnatilgan bo'lsa ishlaydi
            subprocess.run(["node", js_file_path], check=True, capture_output=True)
            
            if os.path.exists(docx_file_path):
                if telegram_id:
                    await send_document(
                        telegram_id, 
                        docx_file_path, 
                        caption=f"🎉 Maqolangiz barcha 6 zanjir (Chain) orqali muvaffaqiyatli tayyorlandi!\n\nMavzu: {topic}"
                    )
            else:
                if telegram_id:
                    await send_status_message(telegram_id, "❌ DOCX fayli Node skripti tomonidan yaratilmadi.")
        except Exception as e:
            print(f"[ArticlePipeline] Node xatosi: {e}")
            if telegram_id:
                await send_status_message(telegram_id, f"❌ Node.js skriptni ishga tushirishda xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.\nXato: {e}")
