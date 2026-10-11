# Bot uchun PRO shablonlar

14 ta soha yoki dizayn to‘plamidagi 31 ta original dizayn 20 slayd va 4 reja bandiga tayyorlandi. Ushbu to‘plamlarning har bir PPTX fayli 5 000 000 baytdan kichik. Manbadagi 16:9 o‘lcham, fon, ranglar, shrift oilalari va dekorativ elementlar saqlanadi. Matn tahrirlanadigan PowerPoint obyektlarida qoladi. Qismlarga bo‘lingan sarlavhalar zarur joylarda bitta matn qutisiga birlashtirildi. Namuna raqamli diagrammalar uchun ajratilgan manba sahifalari ishlatilmagan.

Katta rasmlar siqiladi va katta shriftlardan Latin, kirill, yunon, tinish hamda matematik belgilar qismi saqlanadi. Murakkab SVG bezaklar fayl hajmining asosiy qismini egallasa, 5 MB chegarasiga yetish uchun ayrimlarining manba ichidagi PNG/JPEG nusxasi ishlatiladi. Matn va rasm joylari tekis suratga aylantirilmaydi.

| Soha kodi | Variant | Slayd | Hajm | Almashtiriladigan foto |
|---|---:|---:|---:|---:|
| fizika | 1 | 20 | 0.80 MB | 0 |
| fizika | 2 | 20 | 0.40 MB | 1 |
| english | 1 | 20 | 0.33 MB | 0 |
| english | 2 | 20 | 1.07 MB | 0 |
| english | 3 | 20 | 1.27 MB | 4 |
| cyber | 1 | 20 | 3.42 MB | 15 |
| cyber | 2 | 20 | 1.25 MB | 0 |
| huquq | 1 | 20 | 1.70 MB | 8 |
| huquq | 2 | 20 | 1.34 MB | 6 |
| geografiya | 1 | 20 | 3.82 MB | 2 |
| geografiya | 2 | 20 | 2.21 MB | 2 |
| tibbiyot | 1 | 20 | 1.00 MB | 1 |
| tibbiyot | 2 | 20 | 0.40 MB | 1 |
| tarix | 1 | 20 | 2.51 MB | 5 |
| tarix | 2 | 20 | 0.69 MB | 0 |
| sport | 1 | 20 | 2.57 MB | 16 |
| sport | 2 | 20 | 3.58 MB | 12 |
| moliya | 1 | 20 | 1.32 MB | 5 |
| moliya | 2 | 20 | 0.41 MB | 0 |
| minimalizm | 1 | 20 | 0.26 MB | 0 |
| minimalizm | 2 | 20 | 0.52 MB | 0 |
| matematika | 1 | 20 | 0.89 MB | 2 |
| matematika | 2 | 20 | 2.33 MB | 0 |
| marketing | 1 | 20 | 2.63 MB | 7 |
| marketing | 2 | 20 | 1.68 MB | 13 |
| bolalar | 1 | 20 | 4.98 MB | 5 |
| bolalar | 2 | 20 | 0.69 MB | 0 |
| bolalar | 3 | 20 | 3.25 MB | 0 |
| kimyo | 1 | 20 | 0.61 MB | 0 |
| kimyo | 2 | 20 | 1.53 MB | 0 |
| kimyo | 3 | 20 | 3.03 MB | 0 |

`minimalizm` universal dizayn uslubi. Uning mazmuni foydalanuvchi mavzusiga moslanadi. `bolalar` yoshga mos dars, rivojlanish, o‘yin yoki sayohat mavzusini qo‘llab-quvvatlaydi.

## Fayllar

Har bir to‘plamda:

- `id_N.pptx`: bot to‘ldiradigan shablon.
- `id_N.json`: variantning aniq matn kalitlari, belgi chegaralari, slayd vazifalari va rasm joylari.
- `performance.json`: bot o‘qiydigan sohaviy mazmun va tasvir qoidalari.
- `PERFORMANCE.md`: tuzilish va sohaga mos yozish yo‘riqnomasi.

`{{topic}}`, `{{muallif}}`, `{{reja_1}}`–`{{reja_4}}` umumiy kalitlar. `{{s04_title}}`, `{{s04_text_1}}`, `{{s04_label_1}}` kabi kalitlar alohida slayd bloklariga tegishli. Barcha matnlar tanlangan variantning belgilar chegarasiga sig‘ishi kerak. Asl ism-familiya saqlanadi.

Rasm kalitlari `{{image_N}}` shaklida shape name va alt textda yozilgan. Bir nechta slaydda ishlatilgan asl bir suratning kaliti umumiy. Yangilangan surat alohida relationship oladi va asl crop hamda maskasi saqlanadi. Rasmlar berilmasa asl suratlar qoladi. Foto joyi bo‘lmagan illustrativ variantlar dekorativ elementlarni saqlaydi va rasm generatsiyasi uchun API chaqirmaydi.

## Botda foydalanish

`pro_design` qiymati jadvaldagi soha kodi, `pro_design_variant` esa variant raqami bo‘ladi. Katta-kichik harflar farqlanmaydi. `physics`, `ingliz_tili`, `cybersecurity`, `law`, `geography`, `medicine`, `history`, `sports`, `finance`, `minimalism`, `math`, `mathematics`, `children`, `kids`, `chemistry` aliaslari ham qabul qilinadi.

```python
await pipeline.run(
    topic="Kvadrat tenglamalar", language="uz", author="Sardor O‘rolov",
    is_pro=True, pro_design="matematika", pro_design_variant=2,
    pro_plan_count=4, slide_count=20,
)
```

`GET /presentations/pro-templates` 14 ta to‘plam, 31 ta variant, slayd soni, hajm va foto sonini qaytaradi. Mini App tanlov menyusi shu endpointdan foydalanishi mumkin. Frontend manbalari ushbu repoda mavjud emas.

Bu to‘plamlar uchun slayd soni 20 va reja soni 4 ga tenglashtiriladi. `generate_pro_slides` tanlangan variant sxemasi va sohaviy qoidalarini ishlatadi. Kalit yoki uzunlik xatosida bitta tuzatish so‘rovi yuboriladi, so‘ng natija qat’iy tekshiriladi. Matn bir nechta PowerPoint runlariga bo‘lingan bo‘lsa ham kalit almashtiriladi. Yakuniy PPTX yana optimallashtirilib, 5 MB chegarasi tekshiriladi.

## Alohida faylni to‘ldirish

```bash
python backend/app/services/presentation/fill_template.py \
  backend/app/services/presentation/pro_templates/matematika/id_2.pptx \
  data.json result.pptx --images images.json
```

`data.json` variantdagi barcha matn kalitlarini o‘z ichiga oladi. `images.json` ixtiyoriy: `{"image_1": "photos/example.jpg"}`. Rasm yo‘llari JSON fayliga nisbatan olinadi. `generate_pro_pptx` ishlatilsa fayl hajmi ham cheklanadi.

## Qayta tayyorlash

Papka ichidagi mavjud va qo‘llab-quvvatlanadigan ZIP fayllar uchun:

```bash
python backend/scripts/prepare_subject_templates.py /path/to/zip_files
```

Faqat yangi to‘plamlarni tayyorlash va tekshirish uchun alohida joyga yozish:

```bash
python backend/scripts/prepare_subject_templates.py /path/to/zip_files \
  --subjects tibbiyot tarix sport moliya minimalizm matematika marketing bolalar kimyo \
  --output-root /path/to/staging
```

Oflayn tayyorlash uchun `fonttools` kerak. Botning oddiy ishlashida yangi dependency talab qilinmaydi. Manba ZIP fayllari o‘zgartirilmaydi. Manba dizaynlarining slayd tanlovi tayyorlash skriptida har to‘plam va variant uchun alohida belgilangan.
