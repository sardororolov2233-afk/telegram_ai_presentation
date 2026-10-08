"""Beshta biologiya shabloni uchun umumiy sxema. {{kalit}} formatini saqlang.
Rasm fayllarini media/image_N.jpeg nomi bo‘yicha almashtirmang.
Rasm joylari shape name/alt text orqali {{image_N}} bilan belgilangan.
image_1 va image_2 fon/bezak uchun ixtiyoriy; odatda ularni qoldiring.
"""

FIELD_DESCRIPTIONS = {'topic': 'Taqdimot mavzusi, maksimum 64 belgi.',
 'muallif': 'Muallifning ism-familiyasi, maksimum 50 belgi.',
 'ism_sharif': 'muallif kaliti uchun muqobil nom; bir xil qiymat.',
 'ism_familya': 'muallif kaliti uchun muqobil nom; bir xil qiymat.',
 'yakun': 'E’tiboringiz uchun rahmat! kabi minnatdorchilik, maksimum 35 belgi.',
 'reja': "Bo'lim sarlavhasi: 'Reja' (1 so'z)",
 'kirish': "Bo'lim sarlavhasi: 'Kirish' (1 so'z)",
 'fraza': 'Mavzuning asosiy fikri, 12–20 so‘z, maksimum 150 belgi. Muallifsiz soxta iqtibos '
          'ishlatmang.',
 'kirish_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'fakt_1': "1-fakt sarlavhasi (2-4 so'z)",
 'fakt_1_asosi': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'fakt_2': "2-fakt sarlavhasi (2-4 so'z)",
 'fakt_2_asosi': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'fakt_3': "3-fakt sarlavhasi (2-4 so'z)",
 'fakt_3_asosi': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'analiz': "Bo'lim sarlavhasi: Tahlil / Ko'rsatkichlar (1-3 so'z)",
 'analiz_ustun_nomi': "Jadval 2-ustun sarlavhasi (1-2 so'z, masalan 'Ko'rsatkich')",
 'analiz_ustunlari_1': 'Tekshirilgan biologik ko‘rsatkich yoki sifatli tavsif: 12–18 so‘z, '
                       'maksimum 130 belgi. Raqamni to‘qimang.',
 'analiz_ustunlari_2': 'Tekshirilgan biologik ko‘rsatkich yoki sifatli tavsif: 12–18 so‘z, '
                       'maksimum 130 belgi. Raqamni to‘qimang.',
 'analiz_ustunlari_3': 'Tekshirilgan biologik ko‘rsatkich yoki sifatli tavsif: 12–18 so‘z, '
                       'maksimum 130 belgi. Raqamni to‘qimang.',
 'analiz_ustunlari_4': 'Tekshirilgan biologik ko‘rsatkich yoki sifatli tavsif: 12–18 so‘z, '
                       'maksimum 130 belgi. Raqamni to‘qimang.',
 'line_graph_topic': "Tendensiya tahlili sarlavhasi (2-5 so'z)",
 'birinchi_liniya': "1-tendensiya nomi (2-4 so'z)",
 'birinchi_liniya_sharxi': 'Tendensiya yoki bosqich izohi: 25–40 so‘z, maksimum 280 belgi.',
 'ikkinchi_liniya': "2-tendensiya nomi (2-4 so'z)",
 'ikkinchi_liniya_sharxi': 'Tendensiya yoki bosqich izohi: 25–40 so‘z, maksimum 280 belgi.',
 'uchinchi_liniya': "3-tendensiya nomi (2-4 so'z)",
 'uchinchi_liniya_sharxi': 'Tendensiya yoki bosqich izohi: 25–40 so‘z, maksimum 280 belgi.',
 'gorizantal': 'Biologik jarayon yoki funksiya nomi, 2–4 so‘z, maksimum 40 belgi.',
 'gorizantal_fakt': "Shu jihatga oid bitta aniq fakt (10-18 so'z)",
 'gorizantal_reason': 'Biologik jarayon yoki tuzilishga oid izoh: 35–50 so‘z, maksimum 350 belgi.',
 'vertikal': 'Biologik tuzilish yoki daraja nomi, 2–4 so‘z, maksimum 40 belgi.',
 'vertikal_fakt': "Shu jihatga oid bitta aniq fakt (10-18 so'z)",
 'vertikal_reason': 'Biologik jarayon yoki tuzilishga oid izoh: 35–50 so‘z, maksimum 350 belgi.',
 'positiv_title': "Ustun sarlavhasi: Afzalliklar (1-2 so'z)",
 'positiv': 'Afzalliklar: 25–40 so‘z, maksimum 280 belgi.',
 'negative_title': "Ustun sarlavhasi: Kamchiliklar (1-2 so'z)",
 'negative': 'Cheklovlar: 25–40 so‘z, maksimum 280 belgi.',
 'xulosa': "Bo'lim sarlavhasi: 'Xulosa' (1 so'z)",
 'xulosa_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'adabiyotlar': "Bo'lim sarlavhasi: 'Adabiyotlar' (1-2 so'z)",
 'adabiyotlar_ro_yxati': '6 ta haqiqiy manba, har biri alohida qatorda. Har satr maksimum 100 '
                         'belgi. Muallif, nom, yil yoki URL. Manbalarni to‘qimang.',
 'photo_name': 'Taqdimot vizual mavzusining qisqa nomi',
 'reja_1': "1-reja band sarlavhasi (2-4 so'z)",
 'reja_1_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'reja_2': "2-reja band sarlavhasi (2-4 so'z)",
 'reja_2_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'reja_3': "3-reja band sarlavhasi (2-4 so'z)",
 'reja_3_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.',
 'reja_4': "4-reja band sarlavhasi (2-4 so'z)",
 'reja_4_matni': 'Mavzuga mos aniq biologik izoh: 45–65 so‘z, maksimum 450 belgi.'}

TEXT_LIMITS = {'kirish_matni': {'max_words': 65, 'max_chars': 450},
 'fakt_1_asosi': {'max_words': 65, 'max_chars': 450},
 'fakt_2_asosi': {'max_words': 65, 'max_chars': 450},
 'fakt_3_asosi': {'max_words': 65, 'max_chars': 450},
 'analiz_ustunlari_1': {'max_words': 18, 'max_chars': 130},
 'analiz_ustunlari_2': {'max_words': 18, 'max_chars': 130},
 'analiz_ustunlari_3': {'max_words': 18, 'max_chars': 130},
 'analiz_ustunlari_4': {'max_words': 18, 'max_chars': 130},
 'birinchi_liniya_sharxi': {'max_words': 40, 'max_chars': 280},
 'ikkinchi_liniya_sharxi': {'max_words': 40, 'max_chars': 280},
 'uchinchi_liniya_sharxi': {'max_words': 40, 'max_chars': 280},
 'gorizantal_reason': {'max_words': 50, 'max_chars': 350},
 'vertikal_reason': {'max_words': 50, 'max_chars': 350},
 'positiv': {'max_words': 40, 'max_chars': 280},
 'negative': {'max_words': 40, 'max_chars': 280},
 'xulosa_matni': {'max_words': 65, 'max_chars': 450},
 'reja_1_matni': {'max_words': 65, 'max_chars': 450},
 'reja_2_matni': {'max_words': 65, 'max_chars': 450},
 'reja_3_matni': {'max_words': 65, 'max_chars': 450},
 'reja_4_matni': {'max_words': 65, 'max_chars': 450},
 'topic': {'max_chars': 64},
 'muallif': {'max_chars': 50},
 'fraza': {'max_chars': 150},
 'yakun': {'max_chars': 35}}

def build_schema(topic: str, author: str, pro_plan_count: int = 4) -> dict:
    if pro_plan_count != 4:
        raise ValueError("20 slaydli shablon aynan 4 ta reja bandini talab qiladi")
    s = dict(FIELD_DESCRIPTIONS)
    s["topic"] = f"Mavzu: {topic}. Maksimum 64 belgi."
    for key in ("muallif", "ism_sharif", "ism_familya"):
        s[key] = f"Muallif: {author}. Maksimum 50 belgi."
    s["image_keywords"] = [
        f"Biology visual for {topic}, slot {i}, English specific search phrase"
        for i in range(1, 14)
    ]
    return s
