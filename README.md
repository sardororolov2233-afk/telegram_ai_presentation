# Orzu / Yordamchi AI backend

FastAPI API va Telegram mini ilovasi. Telegram bot kodi alohida [`Orzu`](https://github.com/sardororolov2233-afk/Orzu) reposida. Ikkalasi **bitta Supabase loyihasi** va **bitta Telegram bot tokeni** bilan ishlaydi.

## Amaldagi qoidalar

| Holat | Natija |
|---|---|
| Har 5 ta yangi, tasdiqlangan taklif | Bir oyga 5 ta bepul taqdimot **va** 1 ta kurs ishi |
| Keyingi har 5 ta yangi taklif | Xuddi shu mukofot qayta beriladi |
| Bir oylik obuna | 25 000 so‘m, 10 ta taqdimot |
| Joriy oylik limit tugashi | Yana 5 ta taklif yoki har taqdimot uchun 10 000 so‘m |
| Bepul kurs ishi limiti tugashi | Yana 5 ta taklif yoki 30 000 so‘m / ish |
| Referat / mustaqil ish | 8 000 so‘m, DeepSeek R1-0528 |
| Maqola | 10 000 so‘m, DeepSeek R1-0528 |
| Kurs ishi modeli | DeepSeek R1-0528, yagona sifat |
| To‘lov kartasi | `9860020144204623` |

Bir oy — faollashgan sanadan bir kalendar oy. Obuna avtomatik yangilanmaydi. Faol obunani qayta sotib olib, shu oyning hisoblagichini qayta boshlash mumkin emas. Kurs ishi va referat/maqola obunaga kirmaydi. Kurs mukofoti muddatsiz; taqdimot mukofoti bir oy amal qiladi. Taklif mukofotlari obunadan alohida qo‘shiladi. Avval obunadagi 10 ta, keyin amal qilayotgan taklif kreditlari ishlatiladi. Yangi oylik davr avvalgi davrning foydalanilmagan taqdimotlarini ko‘chirmaydi.

Taklif faqat yangi Telegram ID havola bilan birinchi ro‘yxatdan o‘tganda bog‘lanadi. Orzu bot kanal a’zoligini tekshirgach tasdiqlaydi. Kanalga o‘tish ekranida havola yo‘qolmaydi. O‘zini, avval ro‘yxatdan o‘tgan yoki takroriy foydalanuvchini taklif qilish mukofot bermaydi. Eski foydalanuvchilar migratsiyada yangi taklif sifatida belgilanmaydi.

## Ishga tushirish tartibi

1. Eski bot va backendni to‘xtating; ikkalasi yangi versiyaga o‘tishi kerak. Supabase SQL Editor’da [`backend/supabase/migrations/20261017_commerce.sql`](backend/supabase/migrations/20261017_commerce.sql) faylini **bir marta** bajaring. Orzu reposidagi nusxa aynan shu fayl; ikkalasini alohida bajarish shart emas. Skript qayta bajarilsa balans, obuna va kreditlarni o‘chirmaydi. Mavjud `users`, `payments`, `statistics` jadvallari saqlanadi; eski chek takrorlanish yozuvlari ham ko‘chiriladi. Yangi hisob va mutatsiyalar faqat server `service_role` orqali ochiq; ommaviy Supabase kalitidan foydalanmang.
2. `backend/.env.example` dan `backend/.env` yarating. `SUPABASE_URL`, server uchun `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `OPENROUTER_API_KEY`, kuchli doimiy `SECRET_KEY` ni kiriting. Shu token Orzu’da `BOT_TOKEN` bo‘ladi. `FRONTEND_URL` backendning HTTPS manzili bo‘lsin.
3. Repo ildizida `docker compose up --build -d`. `GET /health` ishlashini va `https://BACKEND_HOST/miniapp` ochilishini tekshiring. Docker LibreOffice hamda PDF uchun shriftlarni o‘rnatadi.
4. Orzu botda `BACKEND_URL=https://BACKEND_HOST` kiriting; yangi mini ilova avtomatik `/miniapp` orqali ochiladi. `MINI_APP_URL` bilan manzilni aniq berish ham mumkin. Botni yangilang.
5. Orzu bot kanal a’zolarini ko‘ra olishi uchun uni belgilangan kanalga admin qiling. BotFather’da backend domenini Web App uchun ruxsat etilgan domen sifatida sozlang.

Backend doim ishlaydigan server/konteynerda ishlaydi: FastAPI lifespan buyurtma ishchilarini ishga tushiradi. Uzoq davom etadigan generatsiyani oddiy qisqa serverless so‘rovga joylashtirmang. `generation_data` volume’ini saqlang; unda kiruvchi rasmlar va natijalar turadi. Bir nechta backend nusxasida shu katalog uchun umumiy fayl saqlash kerak. Hajmni kuzating, eski yuklab olingan natijalarni o‘z saqlash siyosatingiz bo‘yicha tozalang.

**Telegram yangilanishlarini faqat Orzu polling boti qabul qiladi.** Backendning oldingi `/bot/webhook` va ochiq `/bot/set-webhook` yo‘llari ulanmaydi. Bu ikki servisning bir-biridan bot yangilanishlarini olib qo‘yishini to‘xtatadi. Backend tayyor fayllarni shu bot tokeni orqali foydalanuvchiga yuboradi.

## Hisob va buyurtma oqimi

- `POST /api/v1/auth/telegram`: Telegram imzosi va vaqti tekshiriladi, keyin JWT beriladi. Ommaviy test login yo‘q.
- `GET /api/v1/commerce`: balans, kreditlar, keyingi mukofotgacha takliflar, obuna sanasi, narx va havola.
- `POST /api/v1/commerce/subscribe`: balansdan 25 000 so‘mga obuna xaridi. Faol oyda takroriy so‘rov qayta pul yechmaydi.
- `GET /api/v1/presentations/templates`: fanlar va mavjud variantlar.
- `POST /api/v1/presentations/generate`: `topic`, `author`, `language`, `subject`, `variant`, `document_format`, ixtiyoriy `bibliography_text`, `images`. Barcha fan shablonlari yagona mahsulotdir; narx slayd soniga ko‘paytirilmaydi.
- `POST /api/v1/articles/generate`: `topic`, `author`, `language`, ixtiyoriy `references`.
- Generatsiya so‘rovlariga **`Idempotency-Key: <UUID>`** sarlavhasi kerak. Bir buyurtma takror yuborilganda bir marta hisoblanadi; boshqa mazmun bilan shu kalit yuborilsa 409 qaytadi.
- 202 javobidagi `id` orqali `GET /api/v1/jobs/{id}` holatni ko‘rsatadi. Fayl tayyor bo‘lgach `GET /api/v1/jobs/{id}/download`. Boshqa foydalanuvchi buyurtmani ko‘ra/yuklab ola olmaydi.
- Navbat bazada saqlanadi. Ishchi jarayon uzilsa, 3 daqiqalik ijara tugagach ish boshqa ishchiga o‘tadi; uch urinishdan keyin pul/limit qaytariladi. Generatsiya xatosida pul yoki kredit tranzaksiya ichida qaytariladi. Telegram vaqtincha ishlamasa tayyor fayl egasi uchun mini ilovada qoladi. Jarayon uzilishi aynan Telegram yuborish va tasdiqlash orasiga to‘g‘ri kelsa bildirishnoma takrorlanishi mumkin; mijozdan qayta haq olinmaydi.
- Botdagi kurs ishi/referat buyurtmasi uzilib qolsa, eskirgan band qilish avtomatik qaytariladi; foydalanuvchi yangi buyurtma boshlaydi. FSM qoralamalari xotirada saqlanadi.

Obyektivka (10 000 so‘m) va dizayn (5 000 so‘m) API’lari saqlangan; ular ham ayni tranzaksion balansdan foydalanadi. Eski obyektivka interfeysi Orzu’dagi `FRONTEND_URL` orqali ochiladi. Eski taqdimot sifati tanlovi, 2slides integratsiyasi va AI yozgan server kodini bajarish olib tashlangan. Tayyor fan shablonlarining tarixiy `pro_templates` katalog nomi va eski katalogni o‘qish URL’i faqat moslik uchun saqlangan; alohida tarif mavjud emas.

## To‘lov

Botda foydalanuvchi summani/obunani tanlaydi va karta chekini yuboradi. AI tahlili yordamchi ma’lumot; pulni faqat `ADMIN_ID` dagi admin kartaga tushumni tekshirib tasdiqlaydi. `/payments` kutilayotgan cheklarni qayta ochadi. Bir chek takroriy balans bermaydi. Eski 50% balans bonusi olib tashlangan. Faol obunasi bor odam kartaga yana obuna pulini o‘tkazib yuborsa, ikkinchi to‘lov yo‘qolmaydi: balansga qo‘shiladi.

Eski 2slides sinovlarida ochiq yozilgan API kaliti topildi va fayllar olib tashlandi. Eski Git tarixidagi kalit baribir ochiq qolishi mumkin: 2slides hisobida uni bekor qilish kerak. Kodni o‘chirish kalitni bekor qilmaydi.

## Tekshiruvlar

```bash
cd backend
pip install -r requirements-dev.txt
npm ci
npm run test:sql
PYTHONPATH=. pytest -q
```

`npm` faqat PostgreSQL/PGlite sinovlari uchun kerak; ishchi backend Node.js ishlatmaydi. SQL sinovlari taklif chegaralari, qayta bosish, eski chek, muddat, xarid, navbat, qaytarish va ommaviy huquqlarni tekshiradi. API testlari haqiqiy PostgreSQL dvigateli orqali ishlaydi. Yonma-yon `Orzu` checkout’i bo‘lsa, bot → birgalikdagi hisob → API → haqiqiy 20 slaydli PPTX va DOCX integratsiya testi ham bajariladi. AI va Telegram transporti testda almashtirilgan: bu testlar haqiqiy pulli AI yoki bank to‘lovini yubormaydi.

Ishlab turgan Supabase, bot va AI kalitlari bilan oxirgi sinov hamda migratsiyani qo‘llash alohida bajariladi; kod sinovlari ularning amaldagi sozlamalarini tasdiqlamaydi.

## Telegram Serverless bilan ulash

Orzu reposining `codex/telegram-serverless` tarmog‘i shu botni Telegram Serverless’da ishlatadi. Backenddagi yangi academic worker eski Orzu kurs ishi va referat generatorlarini ham navbatda bajaradi. Bitta Supabase loyihasida `backend/supabase/migrations/20261018_serverless.sql` ni oldingi commerce migratsiyasidan keyin bir marta bajaring, keyin shu backendni yangilab qayta ishga tushiring. `/health` da `serverless-academic-queue-v1` ko‘rinishi kerak. Bot deploy’i undan keyin bajariladi. Balanslar va limitlar o‘sha commerce RPC’larida qoladi; eski polling yoki boshqa webhook yangilanish iste’molchisi bilan bir vaqtda ishlamang. Telegram Serverless backend generatsiya worker’ini almashtirmaydi.
