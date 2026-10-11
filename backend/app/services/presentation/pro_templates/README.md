# Bot uchun 5 ta soha shablonlari

11 ta original dizayn 20 slayd va 4 reja bandiga tayyorlandi. Barcha ushbu to‘plamdagi PPTX fayllar 5 000 000 baytdan kichik. Fon, asl naqshlar, ranglar, matn uslublari va 16:9 o‘lcham saqlanadi. Shriftlarning ishlatiladigan yozuvlar qismi saqlanib, katta rasmlar siqildi. Asldagi uydirma diagramma ma’lumotlari to‘plamga ko‘chirilmagan.

| Soha kodi | Variant | Slayd | Hajm | Almashtiriladigan rasm kalitlari |
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

## Fayllar

Har bir sohada:

- `id_N.pptx`: bot to‘ldiradigan shablon.
- `id_N.json`: shu variantning aniq matn kalitlari, belgi chegaralari, slayd vazifalari va rasm joylari.
- `performance.json`: sohaviy mazmun va tasvir qoidalari; bot tomonidan o‘qiladi.
- `PERFORMANCE.md`: taqdimot tuzilishi va sohaga mos yozish yo‘riqnomasi.

`{{topic}}`, `{{muallif}}`, `{{reja_1}}`–`{{reja_4}}` umumiy kalitlar. `{{s04_title}}`, `{{s04_text_1}}`, `{{s04_label_1}}` kabi kalitlar tegishli slaydga tegishli. Alohida bloklar o‘z kalitiga ega, shu sabab bitta paragraf turli bloklarda takrorlanmaydi.

Rasm kalitlari `{{image_N}}` shaklida shape name va alt textda yozilgan. Bir nechta slaydda ishlatilgan asl bir suratning kaliti umumiy. Yangilangan suratlar alohida relationship oladi; boshqa fon yoki bezakni tasodifan o‘zgartirmaydi. Rasmlar berilmasa asl suratlar qoladi. Foto maydoni bo‘lmagan illustrativ variantlar dekorativ rasmlarni saqlaydi va rasm generatsiyasi uchun API chaqirmaydi.

## Botda foydalanish

`pro_design` uchun `fizika`, `english`, `cyber`, `huquq`, `geografiya` qiymatlari, `pro_design_variant` uchun jadvaldagi variant raqami yuboriladi. Masalan:

```python
await pipeline.run(
    topic="Nyuton qonunlari", language="uz", author="Sardor O‘rolov",
    is_pro=True, pro_design="fizika", pro_design_variant=2,
    pro_plan_count=4, slide_count=20,
)
```

`GET /presentations/pro-templates` beshta soha, variantlar, slayd soni va rasm maydonlarini qaytaradi. Uni Mini App tanlov menyusiga ulash mumkin. Frontend manbasi bu repoda mavjud emas; backend barcha yangi sohalarni qabul qiladi.

Yangi sohalarda slayd soni 20 va reja soni 4 ga tenglashtiriladi. `generate_pro_slides` aynan tanlangan variant sxemasini va sohaviy qoidalarni ishlatadi. Kalit yoki uzunlik xatosi bo‘lsa bitta tuzatish so‘rovi yuboriladi, so‘ng natija qat’iy tekshiriladi. Matn kalitlari bir nechta PowerPoint runlariga bo‘lingan holatda ham almashtiriladi. Tayyor PPTX yana optimallashtirilib 5 MB chegarasi tekshiriladi.

## Alohida faylni to‘ldirish

```bash
python backend/app/services/presentation/fill_template.py \
  backend/app/services/presentation/pro_templates/fizika/id_2.pptx \
  data.json result.pptx --images images.json
```

`data.json` shu variantdagi barcha matn kalitlariga ega bo‘lsin. `images.json` ixtiyoriy: `{"image_1": "photos/experiment.jpg"}`. Yo‘llar rasmlar JSON fayliga nisbatan olinadi. Kutubxona orqali `generate_pro_pptx` ishlatilsa hajm cheklovi ham bajariladi.

## Qayta tayyorlash

Asl beshta ZIP fayldan to‘plamni takror yaratish:

```bash
python backend/scripts/prepare_subject_templates.py /path/to/zip_files
```

Bu oflayn buyruq uchun `fonttools` kerak. Botning odatiy ishlashida yangi dependency talab qilinmaydi. Manba ZIP fayllari o‘zgartirilmaydi.
