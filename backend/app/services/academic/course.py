"""Orzu's existing course generation, independent of the Telegram dispatcher."""
import asyncio
import re
from .brain import ask_ai, load_prompt, load_raw_prompt
ai_request = ask_ai

def extract_chapters_from_plan(plan: str) -> dict:
    """
    Rejadagi fasl sonini dinamik aniqlash.
    Qaytaradi: {1: [fasl_nomlari], 2: [fasl_nomlari]}
    """
    chapters = {1: [], 2: []}
    lines = plan.split('\n')

    for line in lines:
        stripped = line.strip()
        # 1.1., 1.2., 1.3. kabi prefiks bilan boshlanuvchi qatorlar
        match = re.match(r'(\d+)\.(\d+)\.?\s+(.*)', stripped)
        if match:
            bob_num = int(match.group(1))
            fasl_title = stripped
            if bob_num in chapters:
                chapters[bob_num].append(fasl_title)

    # Agar hech narsa topilmasa, default 3 ta fasl
    if not chapters[1]:
        chapters[1] = ["1.1.", "1.2.", "1.3."]
    if not chapters[2]:
        chapters[2] = ["2.1.", "2.2.", "2.3."]

    return chapters

def generate_context_summary(section_name: str, content: str) -> str:
    """Fasl mazmunidan qisqa xulosa generatsiya qilish (kontekst chain uchun)"""
    # Matnning birinchi 500 so'zini olish va oxirini olish
    words = content.split()
    if len(words) > 150:
        summary = " ".join(words[:100]) + " ... " + " ".join(words[-50:])
    else:
        summary = content
    return f"[{section_name} xulosasi]: {summary}"

async def generate_full_course_work(topic: str, plan: str, lang: str, status_message=None) -> str:
    """
    Kurs ishini to'liq generatsiya qilish.

    DeepSeek R1-0528 va fasllar orasida kontekst aloqasi.
    """
    full_text = []
    context_chain = []  # Oldingi fasllar xulosasi (C daraja: kontekst chain)

    # Mundarijadagi fasl nomlarini aniqlash
    plan_lines = [line.strip() for line in plan.split('\n') if line.strip()]

    # Dinamik fasl sonini aniqlash (C daraja)
    chapters = extract_chapters_from_plan(plan)
    total_sections = sum(len(sections) for sections in chapters.values())
    if total_sections == 0:
        total_sections = 6

    def get_section_title(prefix):
        for line in plan_lines:
            if line.startswith(prefix):
                return line
        return prefix

    # Til bo'yicha sarlavhalar
    if lang in ("Русский", "Rus"):
        chap_prefixes = {1: "ГЛАВА I", 2: "ГЛАВА II"}
        intro_hdr = "ВВЕДЕНИЕ"
        conc_hdr = "ЗАКЛЮЧЕНИЕ"
        refs_hdr = "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ"
    elif lang in ("Ingliz", "English"):
        chap_prefixes = {1: "CHAPTER I", 2: "CHAPTER II"}
        intro_hdr = "INTRODUCTION"
        conc_hdr = "CONCLUSION"
        refs_hdr = "REFERENCES"
    else:
        chap_prefixes = {1: "I BOB", 2: "II BOB"}
        intro_hdr = "KIRISH"
        conc_hdr = "XULOSA"
        refs_hdr = "FOYDALANILGAN ADABIYOTLAR RO'YXATI"

    async def update_status(text):
        if status_message:
            try:
                await status_message.edit_text(f"⏳ {text}\n\n(DeepSeek R1 | Ish tayyorlanmoqda)")
            except:
                pass

    # ═══════════════════════════════════════════
    # 1. KIRISH
    # ═══════════════════════════════════════════
    await update_status("Kirish qismi yozilmoqda...")

    p_intro = load_raw_prompt("course/21_0_full_intro.txt", topic=topic, plan=plan, language=lang)
    if lang in ["Русский", "Rus"]:
        p_intro += """

ФОРМАТ ТЕКСТА И АБЗАЦЫ (ВАЖНЫЕ ПРАВИЛА):
- Не разбивайте текст на мелкие кусочки, не начинайте каждое предложение с нового абзаца!
- Начинайте абзац в начале раздела и пишите сплошным текстом крупными блоками, не разрывая мысли.
- Начинать с нового абзаца разрешается только после вставки рисунка или таблицы.
- НИКАКИХ СНОСОК (FOOTNOTE) И ИСТОЧНИКОВ ЛИТЕРАТУРЫ ВНУТРИ ТЕКСТА. Никаких [1], (Иванов, 2021) и т.д.! Вся литература пишется только в самом конце работы.
"""
    elif lang in ["English", "Ingliz"]:
        p_intro += """

TEXT FORMAT AND PARAGRAPHS (IMPORTANT RULES):
- Do not split the text into tiny chunks, do not start every new sentence from a new paragraph!
- Start a paragraph at the beginning of the section and write the text in large blocks continuously without breaking thoughts.
- Starting a new paragraph is only allowed after inserting an image or table.
- ABSOLUTELY NO FOOTNOTES OR REFERENCES IN THE TEXT. Do not write [1], (Smith, 2021), etc.! All literature is placed only at the very end of the work.
"""
    else:
        p_intro += """

MATN FORMATI VA ABZASLAR (MUHIM QOIDALAR):
- Matnni mayda bo'laklarga ajratmang, har bir gapni yangi abzasdan boshlamang! Qator tashlab ketma-ket abzatslar yozish TAQIQLANADI.
- Fasl boshida bitta abzasdan boshlang va butun matnni yaxlit bitta yoki ikkita juda yirik abzas shaklida, fikrlarni uzmasdan (bitta qatorda o'zaro bog'lab, davom ettirib) yozing.
- Faqatgina rasm yoki jadval (table) kiritilgandan keyingina yangi abzasdan boshlashingiz mumkin.
- Matn orasida aslo snoska (footnote) yoki adabiyotga havola (masalan, [1], (Ivanov, 2020) va hokazo) qoldirmang! Barcha adabiyotlar faqatgina ishning eng oxirida "Foydalanilgan adabiyotlar" ro'yxatida yoziladi. Matn ichini toza saqlang.
"""
    intro_content = await ai_request(p_intro)

    if intro_content:
        full_text.append(f"{intro_hdr}\n\n{intro_content}")
        context_chain.append(generate_context_summary("KIRISH", intro_content))
    else:
        raise RuntimeError("Kirish yaratilmadi")

    # ═══════════════════════════════════════════
    # 2. BOBLARNI GENERATSIYA QILISH (Kontekst Chain bilan)
    # ═══════════════════════════════════════════
    for i in range(1, 3):  # I va II Boblar
        bob_roman = chap_prefixes[i]
        bob_alt = bob_roman.replace("I", "1").replace("II", "2")

        bob_full_title = get_section_title(bob_roman)
        if bob_full_title == bob_roman:
            bob_full_title = get_section_title(bob_alt)
            if bob_full_title == bob_alt:
                bob_full_title = bob_roman

        full_text.append(f"\n\n{bob_full_title}")

        # Dinamik fasl soni (C daraja)
        chapter_sections = chapters.get(i, ["default"])
        num_sections = len(chapter_sections)

        for j in range(1, num_sections + 1):
            prefix = f"{i}.{j}."
            section_title = get_section_title(prefix)

            await update_status(f"{section_title} kengaytirib yozilmoqda...")

            # Oldingi fasllar kontekstini tayyorlash (C daraja: Context Chain)
            if context_chain:
                previous_context = "OLDINGI FASLLAR KONTEKSTI (takrorlamasdan, davom ettiring):\n" + "\n".join(context_chain[-3:])  # Oxirgi 3 ta fasl
            else:
                previous_context = ""

            # Fasl promptini yuklash
            prompt_file = f"course/22_{i}_chapter{i}_fasl{j}.txt"
            p_fasl = load_raw_prompt(prompt_file, topic=topic, plan=plan, language=lang, previous_context=previous_context)

            # Agar prompt fayl topilmasa (dinamik fasllar uchun), umumiy promptni ishlatish
            if not p_fasl:
                p_fasl = load_raw_prompt("course/21_course_section.txt",
                    topic=topic, plan=plan, section_name=section_title,
                    volume="Kamida 2500 so'z (6 bet)",
                    instructions="Ilmiy akademik uslubda chuqur tahlil bilan yozing.",
                    language=lang)

            # Qat'iy ko'rsatma qo'shish
            if lang in ["Русский", "Rus"]:
                p_fasl += f"""

СТРОГАЯ СИСТЕМНАЯ ИНСТРУКЦИЯ:

Ваша единственная задача: написать только часть "{section_title}" на тему "{topic}".

ЗАПРЕЩЕНО:
❌ Переходить к другим главам.
❌ Лить воду общими фразами.
❌ Начинать текст с "В данном разделе...".
❌ Повторять заголовок внутри текста.
❌ Писать выводы по главе (если это не раздел 2.3 или 1.3).

ОБЯЗАТЕЛЬНО:
✅ Текст должен на 100% соответствовать плану "{plan}".
✅ Каждая мысль должна быть научно обоснована.
✅ Основной текст ОБЯЗАТЕЛЬНО должен быть написан на языке: {lang}. НИКАКИХ УЗБЕКСКИХ СЛОВ ИЛИ ЛАТИНСКИХ БУКВ!

КОНТРОЛЬ ОБЪЕМА И КАЧЕСТВА:
1. Минимальный объем: не менее 2500 слов (6 полных страниц). Проведите глубокий анализ.

ФОРМАТ ТЕКСТА, АБЗАЦЫ И ЦИТАТЫ (СТРОГИЕ ПРАВИЛА):
- Не разбивайте текст на мелкие кусочки, не начинайте каждое предложение с нового абзаца!
- Начинайте абзац в начале раздела и пишите сплошным текстом крупными блоками, не разрывая мысли.
- Начинать с нового абзаца разрешается только после вставки таблицы. В остальных случаях пишите сплошным научным текстом крупными блоками.
- НИКАКИХ СНОСОК (FOOTNOTE) И ИСТОЧНИКОВ ЛИТЕРАТУРЫ ВНУТРИ ТЕКСТА. Никаких [1], (Иванов, 2021) и т.д.! Вся литература пишется только в самом конце работы.
"""
            elif lang in ["English", "Ingliz"]:
                p_fasl += f"""

STRICT SYSTEM INSTRUCTION:

Your only task is to write strictly the "{section_title}" section for the topic "{topic}".

FORBIDDEN:
❌ Jumping to other chapters.
❌ Using generic filler text.
❌ Starting the text with "In this section...".
❌ Repeating the title inside the text.
❌ Writing chapter conclusions (unless it's section 2.3 or 1.3).

MANDATORY:
✅ The text must 100% match the plan "{plan}".
✅ Every point must be scientifically justified.
✅ The main text MUST be strictly written in the language: {lang}. NO UZBEK WORDS!

VOLUME AND QUALITY CONTROL:
1. Minimum volume: At least 2500 words (6 full pages). Provide deep analysis.

TEXT FORMAT, PARAGRAPHS AND CITATIONS (STRICT RULES):
- Do not split the text into tiny chunks, do not start every new sentence from a new paragraph!
- Start a paragraph at the beginning of the section and write the text in large blocks continuously without breaking thoughts.
- Starting a new paragraph is only allowed after inserting a table. Otherwise, continue writing in large blocks.
- ABSOLUTELY NO FOOTNOTES OR REFERENCES IN THE TEXT. Do not write [1], (Smith, 2021), etc.! All literature is placed only at the very end of the work.
"""
            else:
                p_fasl += f"""

QAT'IY TIZIM BUYRUG'I (STRICT SYSTEM INSTRUCTION):

Sizning yagona vazifangiz: "{topic}" mavzusining faqat va faqat "{section_title}" qismini yozish.

TAQIQ (FORBIDDEN):
❌ Boshqa boblarga o'tib ketish.
❌ Umumiy gaplar bilan suvlarni ko'paytirish.
❌ Matnni "Ushbu bo'limda..." deb boshlash.
❌ Sarlavhani matn ichida qaytarish.
❌ Bob uchun xulosa yozish (agar 2.3 yoki 1.3 fasl bo'lmasa).

TALAB (MANDATORY):
✅ Matn "{plan}" rejasiga 100% mos bo'lishi shart.
✅ Har bir fikr ilmiy asoslangan bo'lishi kerak.
✅ Asosiy matn majburiy ravishda quyidagi tilda yozilishi shart: {lang}

HAJM VA SIFAT NAZORATI:
1. Minimal hajm: Kamida 2500 so'z (6 to'liq sahifa) bo'lishi SHART. Chuqur tahlil qiling.

MATN FORMATI, ABZASLAR VA IQTIBOSLAR (QAT'IY QOIDALAR):
- Matnni mayda bo'laklarga ajratmang, har bir yangi gapni yangi abzasdan (qator tashlab) boshlamang!
- Fasl boshida bitta abzasdan boshlang va butun matnni yaxlit bir necha yirik qismlari shaklida, fikrlarni uzmasdan (yangi fikrni ham uzluksiz, abzasni davomidan) yozib keting.
- Faqatgina jadval kiritilgandan keyingina yangi abzasdan boshlashga ruxsat etiladi. Qolgan holatlarda yirik bloklar shaklida, ilmiy tekstni davom ettirib yozing.
- MATN ORASIGA SNOSKA (FOOTNOTE) VA ADABIYOT MANBALARINI ASLO KIRITMANG. Hech qanday [1], (Ahmedov, 2021) ko'rinishidagi ishoralarni yozmang! Barcha adabiyotlar faqat asosiy ishning eng oxirida yoziladi.
"""

            content = await ai_request(p_fasl)

            if content:
                full_text.append(f"\n{section_title}\n{content}")
                # Kontekst chainni yangilash
                context_chain.append(generate_context_summary(section_title, content))
            else:
                raise RuntimeError("Fasl yaratilmadi")

    # ═══════════════════════════════════════════
    # 3. UMUMIY XULOSA
    # ═══════════════════════════════════════════
    await update_status("Yakuniy xulosa tayyorlanmoqda...")

    # Xulosa uchun barcha fasllar kontekstini uzatish
    conclusion_context = ""
    if context_chain:
        conclusion_context = "BARCHA BOBLAR XULOSASI (umumlashtiring):\n" + "\n".join(context_chain)

    conclusion_prompt = load_raw_prompt("course/23_1_general_conclusion.txt",
        topic=topic, plan=plan, language=lang, previous_context=conclusion_context)

    if lang in ["Русский", "Rus"]:
        conclusion_prompt += """

ФОРМАТ ТЕКСТА И АБЗАЦЫ (ВАЖНЫЕ ПРАВИЛА):
- Не разбивайте текст на мелкие кусочки, не начинайте каждую мысль с новой строки!
- Пишите всё заключение сплошным, непрерывным текстом. Никаких сносок или источников литературы внутри текста!
"""
    elif lang in ["English", "Ingliz"]:
        conclusion_prompt += """

TEXT FORMAT AND PARAGRAPHS (IMPORTANT RULES):
- Do not split the text into tiny chunks, do not start every thought from a new line!
- Write the entire conclusion as a solid, continuous text. Absolutely no footnotes or literature references in the text!
"""
    else:
        conclusion_prompt += """

MATN FORMATI VA ABZASLAR (MUHIM QOIDALAR):
- Matnni mayda bo'laklarga ajratib, har bir fikrni yangi qatordan boshlamang!
- Butun xulosani yaxlit, uzluksiz tekst sifatida davom ettirib yozing. Matn orasida aslo snoska yoki adabiyot manbalarini ko'rsatmang!
"""

    conclusion = await ai_request(conclusion_prompt)

    if conclusion:
        full_text.append(f"\n\n{conc_hdr}\n\n{conclusion}")
    else:
        raise RuntimeError("Xulosa yaratilmadi")

    # ═══════════════════════════════════════════
    # 4. ADABIYOTLAR RO'YXATI
    # ═══════════════════════════════════════════
    await update_status("Adabiyotlar ro'yxati tuzilmoqda...")

    ref_prompt = load_raw_prompt("course/25_references.txt", topic=topic, language=lang)
    if not ref_prompt:
        # Fallback: agar yangi prompt topilmasa
        ref_prompt = f"Provide a list of 20 academic references for the course work topic: '{topic}' formatted in standard OTM citation style. The references must be aligned with the {lang} language context. Include at least 4-5 textbooks, 3-4 journal articles, 2-3 laws, and 3-4 foreign language sources. Format each reference properly with author, title, publisher, year, and pages."

    refs = await ai_request(ref_prompt)
    full_text.append(f"\n\n{refs_hdr}\n\n{refs}")

    full_raw_text = "\n\n".join(full_text)

    return full_raw_text
