# Orzu / Yordamchi AI backend

FastAPI backend, tayyor fan shablonlari va Telegram mini ilovasi. Polling bot kodi alohida
[`Orzu`](https://github.com/sardororolov2233-afk/Orzu) reposida. Ikkalasi bir Supabase loyihasi,
bir Telegram bot tokeni va bir xil hisob qoidalaridan foydalanadi.

## Taklif orqali foydalanish

| Amal | Umumiy taklif kvotasiga ta’siri |
|---|---|
| Yangi do‘st taklif havolasi bilan ro‘yxatdan o‘tib, kanal a’zoligini tasdiqlashi | +1 kvota |
| Bitta taqdimot | −1 kvota |
| Bitta dizayn buyurtmasi, 3 ta variant | −1 kvota |
| Bitta kurs ishi | −2 kvota |
| Referat, mustaqil ish, maqola, obyektivka | Bepul, kvota sarflamaydi |

Kvota muddatsiz va **umumiy**: bir kvota taqdimotga sarflansa, uni dizaynga qayta ishlatib
bo‘lmaydi. Obuna, balans to‘ldirish va pulga qo‘shimcha limit sotish o‘chirilgan. Eski balanslar,
cheklar va obuna yozuvlari tarix uchun saqlanadi, yangi foydalanish huquqini bermaydi.
`POST /api/v1/commerce/subscribe` eski mijozlar uchun 410 qaytaradi. Bazadagi obuna va to‘lovni
tasdiqlash RPC’lari ham yopilgan; interfeysni chetlab pul bilan kvota olish mumkin emas.

Taklif faqat avval ro‘yxatdan o‘tmagan Telegram ID’ning birinchi `/start ref_ID` murojaatiga
bog‘lanadi. Bot rasmiy kanal a’zoligini tekshirgach tasdiqlaydi. O‘zini taklif qilish, botlar,
eski foydalanuvchilar, takroriy `/start` va qayta tasdiqlash qo‘shimcha kvota bermaydi.

## AI modellar va rasmlar

- Barcha matnlar, reja, taqdimot mazmuni va dizayn topshirig‘i:
  `anthropic/claude-haiku-5.5`.
- Taqdimot va dizayn rasmlari: `bytedance-seed/seedream-5-0-flash`.
- Bir `OPENROUTER_API_KEY` ikkala model uchun ishlatiladi. Matn — `/api/v1/chat/completions`,
  rasm — OpenRouter’ning `/api/v1/images` endpointi, `n=1`, `resolution=1K`.
- Bir taqdimotga ko‘pi bilan **3 ta rasm generatsiya so‘rovi** yuboriladi. Shablondagi ko‘proq
  rasm joylari shu rasmlardan qayta foydalanadi; har bir joyga mos qirqiladi. Yuklanadigan
  foydalanuvchi rasmlari ham ko‘pi bilan 3 ta, har biri 5 MB.
- Ishchi qayta ishga tushganda bir xil buyurtmaning rasm fayllari va oldindan yozilgan so‘rov
  belgilari qayta ishlatiladi. Noma’lum natijali uzilgan so‘rov qayta yuborilmaydi. Natijada
  jarayon uzilishi ham 3 ta so‘rov chegarasini oshirmaydi. Ayrim rasmlar olinmasa, muvaffaqiyatli
  rasmlar qayta ishlatiladi; hech biri olinmasa, buyurtma bekor bo‘lib kvota qaytadi.
- Boshqa model, Pollinations yoki tasodifiy stock rasmga yashirin o‘tish yo‘q.

Foydalanuvchi pul to‘lamaydi; **model API xarajatlarini loyiha egasi qoplaydi**. Do‘st taklifi
OpenRouter’da bepul token bermaydi.

## Yangilash va ishga tushirish

1. Bot va backendni yangilash vaqtida to‘xtating. Ikkalasi ham shu taklif siyosatiga o‘tishi kerak.
2. Supabase SQL Editor’da oldingi `20261017_commerce.sql` o‘rnatilgan bo‘lsa, faqat
   [`backend/supabase/migrations/20261022_referral_only.sql`](backend/supabase/migrations/20261022_referral_only.sql)
   ni bajaring. Yangi bazada ikkala migratsiyani sana tartibida bajaring. Bot reposidagi nusxalar
   aynan shu fayllar — umumiy bazada bir marta bajarish yetarli.
3. Yangi migratsiya qayta bajarilganda kvota yana berilmaydi. Eski ishlatilmagan taklif mukofotlari
   umumiy kvotaga o‘tadi: taqdimot krediti 1, kurs krediti 2 birlik. Eski 5 kishilik chegaraga
   yetmagan tasdiqlangan takliflar ham 1 birlikdan hisoblanadi. Eski band qilingan ishlar xatoda
   bir marta qaytariladi. Pul yoki obuna taklif kvotasiga aylantirilmaydi.
4. `backend/.env.example` bo‘yicha `backend/.env` sozlang: `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`,
   `OPENROUTER_API_KEY`, doimiy kuchli `SECRET_KEY`, `FRONTEND_URL`.
5. Repo ildizida `docker compose up --build -d`; yoki backend katalogidan
   `uvicorn app.main:app --host 0.0.0.0 --port 8100`. `GET /health`, `/miniapp` va
   `/static/miniapp.js` ishlashini tekshiring. Docker PDF uchun LibreOffice va shriftlarni o‘rnatadi.
6. Botga `BACKEND_URL=https://BACKEND_HOST`, shu Supabase va OpenRouter kalitlari, ayni
   `BOT_TOKEN` ni sozlang. Botni rasmiy kanalga admin qiling va ishga tushiring.

Ikkala dastur ham yangi `commerce_policy` RPC’siz ishga tushmaydi. Bu eski pulli SQL qoidalari
bilan yangi interfeys aralashib ishlashining oldini oladi. RPC va hisob jadvallariga faqat server
`service_role` kaliti kiradi; foydalanuvchiga bu kalit berilmaydi.

`JOB_STORAGE_DIR` doimiy disk bo‘lsin. Bir nechta backend nusxasida umumiy disk kerak: navbat
Postgres’da, rasmlar va hujjatlar shu diskda saqlanadi. Tugagan buyurtmaning vaqtinchalik rasmlari
tozalanadi, tayyor hujjati yuklab olish uchun qoladi. Faqat Orzu polling boti Telegram yangilanishlarini
qabul qiladi; parallel webhook yoqilmaydi.

## API oqimi

- Telegram imzosi va vaqti `POST /api/v1/auth/telegram` da tekshiriladi; JWT beriladi.
- `GET /api/v1/commerce`: `access_mode=referral_only`, `referral_credits`, `quota_costs`,
  taklif havolasi va barcha xizmatlarning kvota takliflari. `course_credits` va
  `referral_presentations` umumiy balansni ifodalovchi muqobil hisoblar; alohida hamyonlar emas.
- `GET /api/v1/presentations/templates`: mavjud fan shablonlari.
- `POST /api/v1/presentations/generate` va `/articles/generate`: `Idempotency-Key: UUID`
  bilan 202 va navbat identifikatori qaytadi. Bir buyurtma qayta yuborilsa kvota yana olinmaydi;
  boshqa mazmun bilan bir UUID ishlatilsa 409 qaytadi.
- `GET /api/v1/jobs/{id}` va `/download` faqat buyurtma egasiga ochiq. Ishchi uzilganda navbat
  qayta olinadi; xatoda band qilingan kvota tranzaksiya ichida qaytariladi.
- `POST /api/v1/designs/generate`: tavsif, format, uslub, til; Seedream’ning 3 ta PNG varianti.
  Yangi mini ilova `Idempotency-Key` yuboradi; shu kalitning takrori generatsiya qilmaydi va 409
  qaytaradi. Dizayn natijasi sinxron javobda beriladi; u navbatdagi hujjat emas.

Mini ilova `/miniapp?tab=presentations`, `?tab=articles`, `?tab=designs`, `?tab=account`
oynalarini qo‘llaydi. Obuna yoki karta orqali to‘lash tugmalari yo‘q.

## Tekshiruvlar

```bash
cd backend
pip install -r requirements-dev.txt
npm ci
npm run test:sql
PYTHONPATH=. pytest -q
node --check static/miniapp.js
```

SQL sinovlari haqiqiy PostgreSQL dvigateli (PGlite) orqali eski siyosatdan o‘tish, takroriy
migratsiya, har taklifga bir kvota, umumiy balans, kursning ikki birlik narxi, qaytarish,
bir vaqtdagi so‘rovlar, eski to‘lovni bloklash va ommaviy huquqlarni tekshiradi.
Python sinovlari API → baza → PPTX/DOCX, Haiku/Seedream transporti, rasm chegarasi va
jarayon uzilgandagi qayta foydalanishni tekshiradi. Yonma-yon `orzu-bot` yoki `Orzu` checkout’i
bo‘lsa, bot → taklif → API → fayl sinovi ham bajariladi; yo‘lni `ORZU_BOT_PATH` bilan berish mumkin.
AI va Telegram sinov transportlari almashtiriladi: testlar haqiqiy pulli API yoki xabar yubormaydi.

Ishlab turgan Supabase’da migratsiya bajarilgani, server yangilangani va haqiqiy OpenRouter
kaliti ikkala modelga kira olishi alohida ishga tushirish tekshiruvini talab qiladi.
