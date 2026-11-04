# Telegram Serverless ommaviy xabarlari

Botning admin panelida matn, rasm yoki video yuborilib, **Yuborish** bir marta
tasdiqlangach, Alwaysdata ishchisi mavjud foydalanuvchilarga avtomatik tarqatadi.
Har 15 kishidan keyin tugma bosish kerak emas. Xabarning formatlari va mediasi
Telegram `copyMessage` orqali saqlanadi. Yangi tasdiqsiz yangi tarqatish boshlanmaydi.

`ADMIN_ID` botdagi admin ID bilan bir xil bo‘lsin; bir nechta ID vergul bilan
ajratiladi. Backend va Serverless ayni `SUPABASE_SERVICE_ROLE_KEY` (yoki backenddagi
`SUPABASE_KEY`) hamda ayni bot tokenidan foydalanishi kerak. API umumiy kalitdan
alohida hosil qilingan server sarlavhasi bilan himoyalangan; foydalanuvchi JWT’si
bu endpointlarga kirish bermaydi. Yangi token yoki SQL migratsiyasi kerak emas.

Alwaysdata `backend/.env` qo‘shimchalari:

```dotenv
ADMIN_ID=BOTDAGI_ADMIN_TELEGRAM_ID
BROADCAST_STORAGE_DIR=/home/sardorbekuralov/orzu-broadcasts
BROADCAST_RATE_PER_SECOND=25
```

Yo‘l doimiy va sayt ishlaydigan foydalanuvchi uchun yoziladigan bo‘lsin. Bu alohida
sozlama mavjud `JOB_STORAGE_DIR` va undan yuklab olinayotgan hujjatlarni o‘zgartirmaydi.
`BROADCAST_STORAGE_DIR` berilmasa `JOB_STORAGE_DIR/broadcasts` ishlatiladi. Backendni
yangilab qayta ishga tushiring. `GET /health` ichida `serverless-broadcast-v1` paydo
bo‘lgach bot yuborishga ruxsat beradi. Python muhiti uchun tekshirilgan FastAPI
versiyasi `fastapi==0.115.14`; mavjud o‘rnatishni shu versiyada saqlang.

Ishchi 500 tadan kalit asosida sahifalaydi; bu umumiy foydalanuvchilar cheklovi emas.
Boshlashdagi vaqt va eng katta Telegram ID chegarasi saqlanadi, keyin qo‘shilgan
foydalanuvchilar shu tarqatishga qo‘shilmaydi. Oldingi qo‘lda yuborilgan 15 talik
tarqatish davom ettirilganda uning kursori va hisoblari ham ko‘chiriladi.

Odatiy tezlik soniyasiga 25 ta urinish, bir paytda ko‘pi bilan 5 ta so‘rov. Sozlama
1–28 oralig‘ida cheklanadi: Telegram’ning taxminan 30 xabar/soniya bepul umumiy
chegarasida botning oddiy javoblari uchun joy qoladi. Bu kafolatlangan yetkazish
tezligi emas; tarmoq va Telegram cheklovlari uni kamaytirishi mumkin. Pulli
`allow_paid_broadcast` yoqilmaydi. Telegram `429` qaytarsa, `retry_after` butun
tarqatishni kutishga qo‘yadi va o‘sha qabul qiluvchi qayta sinaladi. Kutish va
jarayon SQLite’da saqlanadi, restartdan keyin ham davom etadi.

Botni bloklagan yoki o‘chirilgan akkaunt bitta muvaffaqiyatsiz qabul qiluvchi sifatida
qayd etiladi. Manba xabar yo‘qolishi, token xatosi yoki davomli tarmoq xatosi butun
tarqatishni pauzaga qo‘yadi. Admin panelidagi holat, davom ettirish va bekor qilish
tugmalari shu ishga murojaat qiladi. Bekor qilishdan oldin boshlangan ko‘pi bilan
5 ta so‘rov yakunlanishi mumkin. Yakuniy admin xabari bir marta uriniladi; yetkazib
bo‘lmasa, holat panel orqali ko‘rinadi.

Bitta tarqatish faol bo‘ladi; takroriy tasdiq bir xil ish identifikatorini qaytaradi.
Saqlangan muvaffaqiyatli qabul qiluvchilar qayta yuborilmaydi. Telegram javobi
yo‘qolishi yoki yuborish bilan SQLite qaydi orasida jarayon uzilishida o‘sha noaniq
qabul qiluvchiga dubl xabar tushishi mumkin: Telegram `copyMessage` uchun
idempotency kalitini bermaydi. Shu cheklovdan tashqari ma’lum natijalar saqlanadi.

SQLite va `flock` bitta Alwaysdata hostidagi bir nechta Uvicorn jarayoni orasida
yagona yuboruvchini ta’minlaydi. Bir xil botning tarqatuvchisini boshqa hostlarda
parallel ishga tushirmang. Doimiy katalogni o‘chirish tarix va kursorga zarar yetkazadi.
Mahalliy testlar Telegram va foydalanuvchilar ro‘yxatini almashtiradi, haqiqiy
foydalanuvchilarga hech qanday sinov xabari yubormaydi.
