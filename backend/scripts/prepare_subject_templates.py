"""Prepare the five supplied ZIP archives for the bot, preserving OOXML artwork.

Usage: python backend/scripts/prepare_subject_templates.py /path/to/uploads
Offline preparation additionally requires fonttools. Never edits input ZIPs.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
import posixpath
import re
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.presentation.pptx_assets import compact_images, prune_parts, subset_embedded_fonts, write_package, optimize_pptx

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main", "p": "http://schemas.openxmlformats.org/presentationml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
ROOT = Path(__file__).resolve().parents[1] / "app/services/presentation/pro_templates"

# Source slide numbers in the supplied designs. Fake example charts, blank
# pages and unused resource galleries are deliberately excluded.
ORDERS = [
 [1,2,2,4,5,6,7,8,9,10,5,4,7,8,9,10,11,3,2,12],
 [1,11,2,3,4,5,6,7,9,10,4,5,7,8,9,11,10,3,11,12],
 [1,2,2,4,5,11,6,7,12,8,9,13,4,5,15,11,2,15,2,10],
 [1,3,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,17,3,19],
 [1,2,3,5,6,7,4,5,6,7,11,14,5,6,7,11,14,9,3,15],
 [1,2,3,4,5,6,3,4,5,6,3,4,5,6,8,4,8,4,4,10],
 [1,7,3,4,5,6,7,8,4,5,6,7,8,4,5,8,10,5,7,12],
 [1,6,3,4,5,6,7,8,9,4,5,6,7,8,9,5,11,9,6,12],
 [1,2,2,3,4,5,2,3,4,5,2,3,4,5,7,5,7,5,2,10],
 [1,2,2,3,4,5,6,7,8,9,2,3,4,5,6,8,10,5,2,1],
 [1,8,2,3,4,5,6,7,8,9,3,4,5,6,7,8,9,6,2,10],
]
SUBJECTS = {
 "fizika": {"label": "Fizika", "guidance": "Har bir qonunni qo‘llanish sharti bilan tushuntiring. Formulada belgilarni va SI birliklarini oching. Berilgan, formula, hisoblash va javob ketma-ketligida bitta yechilgan misol keltiring. Tajriba natijasini kuzatuv va talqin bilan ajrating. O‘lchov xatoligini tushuntiring. Sonlarni to‘qimang.", "sections": ["Tushuncha va kattaliklar", "Qonun va formulalar", "Tajriba va kuzatuv", "Amaliy qo‘llanish"], "image_rule": "Mavzuga mos fizik qurilma yoki tajriba fotosi. Aniq formula, grafik va o‘lchov belgilari matnda qoladi."},
 "english": {"label": "Ingliz tili", "guidance": "Mavzuga mos til ko‘nikmasini o‘rgating. Umumiy daraja B1–B2, agar mavzu boshqa darajani talab qilsa moslang. Qoida, tabiiy inglizcha misol, qisqa izoh va mashqni ajrating. Inglizcha misolni tarjima bilan almashtirmang. So‘z birikmalarini kontekstda qo‘llang. Mashq javobi va xato sababini ko‘rsating.", "sections": ["Meaning and vocabulary", "Rules and structure", "Examples in context", "Practice and feedback"], "image_rule": "O‘rganilayotgan vaziyatga mos sodda foto yoki illustratsiya. Matn va grammatika rasm ichida yozilmasin."},
 "cyber": {"label": "Kiberxavfsizlik", "guidance": "Aktiv, tahdid, zaiflik va himoya choralarini aniq farqlang. Tahdidni real hayotga yaqin, uydirma deb belgilangan vaziyat orqali tushuntiring. Aniqlash, oldini olish va tiklanish ketma-ketligini ko‘rsating. Hujum ko‘rsatmalaridan ko‘ra himoya va ruxsatli laboratoriya ta’limiga e’tibor bering. Statistika va standart raqamini to‘qimang.", "sections": ["Aktivlar va xavfsizlik", "Tahdid va zaifliklar", "Himoya usullari", "Hodisa va tiklanish"], "image_rule": "Mavzuga mos qurilma yoki himoya vaziyati. Shaxsiy ma’lumotlar, haqiqiy parollar va soxta interfeys yozuvlari ko‘rsatilmasin."},
 "huquq": {"label": "Huquq", "guidance": "Mavzu qaysi yurisdiksiyaga tegishli ekanini aniqlang. Mamlakat, hujjat nomi va tahrir sanasi noma’lum bo‘lsa aniq modda raqami yoki amaldagi norma haqida taxmin yozmang. Huquqiy tushuncha, norma, uydirma o‘quv vaziyati va tahlilni ajrating. Huquq va majburiyatni farqlang. Tekshirilmagan sud qarori, jazo miqdori yoki qonun manbasini keltirmang.", "sections": ["Tushuncha va manbalar", "Huquqiy norma", "Vaziyat va tahlil", "Huquqni himoya qilish"], "image_rule": "Huquqiy institut, hujjat yoki kasbiy vaziyatga mos foto. Fotosurat aniq real sud ishi dalili deb talqin qilinmasin."},
 "geografiya": {"label": "Geografiya", "guidance": "Hududning o‘rni va miqyosini ko‘rsating. Tabiiy hamda ijtimoiy jarayonlarni sabab va oqibat bilan tushuntiring. Sonli ko‘rsatkichga birlik, hudud, yil va manba kerak. Xarita uchun koordinata, yo‘nalish va legendani faqat tekshirilgan ma’lumot asosida yozing. Uydirma koordinata yoki xarita bermang. Hududlar solishtirishida bir xil davr va birlikdan foydalaning.", "sections": ["Geografik o‘rin", "Tabiiy sharoit", "Hududiy jarayonlar", "Taqqoslash va muammolar"], "image_rule": "Hudud yoki tabiiy jarayonning haqiqiy fotosi. Ilmiy xaritani generativ foto bilan almashtirmang; xarita uchun foydalanuvchi tasdiqlagan fayl kerak."},
}


def xml(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def text(shape):
    return "".join(shape.xpath(".//a:t/text()", namespaces=NS)).strip()


def size(shape):
    sizes = shape.xpath(".//a:rPr/@sz|.//a:defRPr/@sz", namespaces=NS)
    return max([int(n) / 100 for n in sizes] or [24])


def set_text(shape, value, cap=None):
    body = shape.find("p:txBody", NS)
    if body is None:
        return
    pars = body.findall("a:p", NS)
    first = copy.deepcopy(pars[0]) if pars else ET.Element("{" + NS["a"] + "}p")
    run = copy.deepcopy(next(iter(first.findall("a:r", NS)), ET.Element("{" + NS["a"] + "}r")))
    for child in list(first):
        if child.tag != "{" + NS["a"] + "}pPr":
            first.remove(child)
    for child in list(run):
        if child.tag != "{" + NS["a"] + "}rPr":
            run.remove(child)
    rp = run.find("a:rPr", NS)
    if rp is None:
        rp = ET.SubElement(run, "{" + NS["a"] + "}rPr")
    if cap and size(shape) > cap:
        rp.set("sz", str(round(cap * 100)))
    for p in pars:
        body.remove(p)
    for line in value.split('\n'):
        paragraph = copy.deepcopy(first)
        item = copy.deepcopy(run)
        ET.SubElement(item, "{" + NS["a"] + "}t").text = line
        paragraph.append(item)
        body.append(paragraph)
    props = body.find("a:bodyPr", NS)
    if props is not None:
        props.set("wrap", "square")
        for node in list(props):
            if ET.QName(node).localname in ("noAutofit", "normAutofit", "spAutoFit"):
                props.remove(node)
        ET.SubElement(props, "{" + NS["a"] + "}normAutofit")


def budget(shape, kind):
    xf = shape.find("p:spPr/a:xfrm", NS)
    ext = xf.find("a:ext", NS) if xf is not None else None
    if ext is None:
        return 32 if kind == "title" else 160
    w, h = int(ext.get("cx")) / 12700, int(ext.get("cy")) / 12700
    font = size(shape)
    chars_per_line = max(4, math.floor((w - 12) / (font * .61)))
    lines = max(1, math.floor((h - 4) / (font * 1.28)))
    # Short single-line and rotated headings must retain their real capacity.
    # A minimum of fourteen characters would force them into nearby content.
    estimate = max(4, math.floor(chars_per_line * lines * .78))
    if kind == "title":
        return min(48, estimate)
    if kind == "label":
        return min(54, estimate)
    return min(420, max(8, estimate))


def display_dimensions(shape):
    xf = shape.find("p:spPr/a:xfrm", NS)
    if xf is None: return (0,0)
    ext = xf.find("a:ext", NS)
    if ext is None: return (0,0)
    w,h = int(ext.get("cx")),int(ext.get("cy"))
    parent = shape.getparent()
    while parent is not None:
        if parent.tag == "{"+NS["p"]+"}grpSp":
            group_xf = parent.find("p:grpSpPr/a:xfrm", NS)
            ge = group_xf.find("a:ext", NS) if group_xf is not None else None
            ce = group_xf.find("a:chExt", NS) if group_xf is not None else None
            if ge is not None and ce is not None:
                w *= int(ge.get("cx"))/max(1,int(ce.get("cx")))
                h *= int(ge.get("cy"))/max(1,int(ce.get("cy")))
        parent = parent.getparent()
    return w,h


def role(number):
    if number == 1: return "cover"
    if number == 2: return "agenda"
    if number == 3: return "introduction"
    if 4 <= number <= 15:
        return ("concept", "explanation", "example")[(number - 4) % 3]
    return {16: "application", 17: "conclusion", 18: "questions", 19: "references", 20: "closing"}[number]


def prepare(raw: bytes, source_name: str, subject: str, variant: int, order: list[int]):
    with ZipFile(io.BytesIO(raw)) as package:
        parts = {n: package.read(n) for n in package.namelist()}
    p = ET.fromstring(parts["ppt/presentation.xml"])
    prel = ET.fromstring(parts["ppt/_rels/presentation.xml.rels"])
    ct = ET.fromstring(parts["[Content_Types].xml"])
    # Keep layouts, masters, theme and fonts. Rewrite only the slide sequence.
    for item in list(prel):
        if item.get("Type", "").endswith("/slide"):
            prel.remove(item)
    for lst in p.findall("p:sldIdLst", NS):
        p.remove(lst)
    lst = ET.Element("{" + NS["p"] + "}sldIdLst")
    p.insert(1 if p.find("p:sldMasterIdLst", NS) is not None else 0, lst)
    for entry in list(ct):
        if re.fullmatch(r"/ppt/slides/slide\d+\.xml", entry.get("PartName", "")):
            ct.remove(entry)
    fields = {"topic": {"kind": "title", "max_chars": 48, "description": "Mavzuning qisqa nomi, mazmunini saqlang."}, "muallif": {"kind": "label", "max_chars": 42, "description": "Foydalanuvchi bergan ism-familiya."}, "yakun": {"kind": "title", "max_chars": 24, "description": "Qisqa minnatdorchilik."}}
    slides = []
    image_slots = {}
    source_targets = {}
    new_slides = {}
    for number, src_number in enumerate(order, 1):
        source_part = f"ppt/slides/slide{src_number}.xml"
        root = ET.fromstring(parts[source_part])
        rel_path = f"ppt/slides/_rels/slide{src_number}.xml.rels"
        rel = ET.fromstring(parts[rel_path]) if rel_path in parts else ET.Element("{" + REL + "}Relationships")
        for item in list(rel):
            if item.get("Type", "").endswith(("/notesSlide", "/slide", "/hyperlink")):
                rel.remove(item)
        for link in list(root.xpath("//a:hlinkClick|//a:hlinkMouseOver", namespaces=NS)):
            link.getparent().remove(link)
        # Remove fixed sample data charts rather than passing invented values.
        for chart in root.xpath("//p:graphicFrame[a:graphic/a:graphicData/*[local-name()='chart']]", namespaces=NS):
            chart.getparent().remove(chart)
        current_role = role(number)
        section = (number - 4) // 3 + 1 if 4 <= number <= 15 else None
        rec = {"number": number, "role": current_role, "section": section, "source_slide": src_number, "text_keys": [], "image_keys": []}
        shapes = root.xpath("//p:sp[p:txBody]", namespaces=NS)
        active = []
        cleared_authors = []
        for sh in shapes:
            old = text(sh)
            if not old: continue
            # Source website/menu labels are not teaching content.
            if old in {"Home", "About Us", "Content", "Contact Us", "Studio Shodwe", "Liceria Firm", "Borcelle", "UNION CONSULTING"} or re.search(r"reallygreatsite|Wardiere|\+123", old, re.I):
                if old in {"Studio Shodwe", "Liceria Firm", "Borcelle", "UNION CONSULTING"} or 'Wardiere' in old:
                    cleared_authors.append(sh)
                set_text(sh, "")
                continue
            if re.fullmatch(r"\d+\.?", old):
                set_text(sh, "")
                continue
            active.append(sh)
        if not active:
            raise ValueError(f"No editable text: {source_name}, slide {src_number}")
        heading = max(active, key=size)
        if subject == "cyber" and variant == 1 and number == 1:
            # The source padlock extends over the left edge of the title box.
            # Keep generated one-line titles completely to its right.
            xf = heading.find("p:spPr/a:xfrm", NS)
            xf.find("a:off", NS).set("x", "8000000")
            xf.find("a:ext", NS).set("cx", "8510596")
        set_text(heading, "{{topic}}" if number == 1 else "{{yakun}}" if number == 20 else "{{reja}}" if number == 2 else "{{adabiyotlar}}" if number == 19 else f"{{{{s{number:02}_title}}}}", cap=100 if number in (1,20) else 72)
        if subject == "english" and variant == 3 and number in (1, 20):
            # The source's white headings vanish on its pale paper/yellow.
            for rp in heading.findall(".//a:rPr", NS):
                for fill in list(rp):
                    if ET.QName(fill).localname in ("solidFill", "gradFill", "noFill"):
                        rp.remove(fill)
                fill = ET.Element("{" + NS["a"] + "}solidFill")
                ET.SubElement(fill, "{" + NS["a"] + "}srgbClr", val="141414")
                rp.insert(0, fill)
        if number == 1 or number == 20:
            key = "topic" if number == 1 else "yakun"
            fields[key]["max_chars"] = min(fields[key]["max_chars"], budget(heading, "title"))
        else:
            key = "reja" if number == 2 else "adabiyotlar" if number == 19 else f"s{number:02}_title"
            fields[key] = {"kind": "title", "max_chars": budget(heading, "title"), "slide": number, "role": current_role, "section": section, "description": "Slayd mazmunini bildiruvchi qisqa sarlavha."}
        rec["text_keys"].append(key)
        others = [sh for sh in active if sh is not heading]
        if number in (1,20):
            if not others:
                # Reuse the original author/brand box cleared above.
                others = cleared_authors
            if others:
                set_text(others[-1], "{{muallif}}", cap=36)
                rec["text_keys"].append("muallif")
                for sh in others[:-1]: set_text(sh, "")
        elif number == 2:
            if not others: raise ValueError("Agenda needs a text box")
            body = max(others, key=lambda sh: len(text(sh)))
            separate = len(others) == 4
            if not separate:
                # The four agenda entries occupy separate paragraphs in one box.
                set_text(body, "{{reja_1}}\n{{reja_2}}\n{{reja_3}}\n{{reja_4}}", cap=36)
            total = budget(body, "text")
            for i in range(1,5):
                name = f"reja_{i}"
                if separate:
                    set_text(others[i-1], "{{"+name+"}}", cap=36)
                fields[name] = {"kind": "label", "max_chars": min(36,budget(others[i-1],"text")) if separate else min(36, max(14, total // 4)), "section": i, "description": "Mavzuga mos reja bandi."}
                rec["text_keys"].append(name)
            if not separate:
                for sh in others:
                    if sh is not body: set_text(sh, "")
        elif number == 19:
            if not others: raise ValueError("References needs a text box")
            body = max(others, key=lambda sh: len(text(sh)))
            set_text(body, "{{adabiyotlar_ro_yxati}}", cap=28)
            # Expand only the source text box inside its existing safe region.
            fields["adabiyotlar_ro_yxati"] = {"kind": "references", "role": "references", "max_chars": min(420, budget(body, "text")), "slide": 19, "description": "3–4 ta haqiqiy yoki foydalanuvchi bergan manba. Har biri yangi qatorda. Soxta manba yoki URL yozmang."}
            rec["text_keys"].append("adabiyotlar_ro_yxati")
            for sh in others:
                if sh is not body: set_text(sh, "")
        else:
            label_count = body_count = 0
            for sh in others:
                old = text(sh)
                kind = "label" if len(old) < 90 and (size(sh) >= 40 or not old.endswith(('.', '!', '?'))) else "text"
                if kind == "label": label_count += 1; serial = label_count
                else: body_count += 1; serial = body_count
                key = f"s{number:02}_{'label' if kind == 'label' else 'text'}_{serial}"
                set_text(sh, "{{" + key + "}}", cap=42 if kind == "label" else None)
                fields[key] = {"kind": kind, "max_chars": budget(sh, kind), "slide": number, "role": current_role, "section": section, "description": "Shu slaydga tegishli alohida " + ("qisqa kichik sarlavha." if kind == "label" else "izoh. Qo‘shni blok mazmunini takrorlamang.")}
                rec["text_keys"].append(key)
        relationships = {v.get("Id"): v for v in rel}
        for sh in root.xpath("//p:pic|//p:sp[p:spPr/a:blipFill]", namespaces=NS):
            blip = sh.find(".//a:blip", NS)
            xf = sh.find("p:spPr/a:xfrm", NS)
            if blip is None or xf is None: continue
            ext = xf.find("a:ext", NS)
            if ext is None: continue
            rid = blip.get("{" + NS["r"] + "}embed")
            relation = relationships.get(rid)
            if relation is None: continue
            target = posixpath.normpath(posixpath.join("ppt/slides", relation.get("Target")))
            data = parts.get(target)
            if not data: continue
            display_w,display_h = display_dimensions(sh)
            area = display_w * display_h / (18288000 * 10287000)
            if not .012 < area < .72: continue
            try:
                with Image.open(io.BytesIO(data)) as im:
                    opaque = im.mode != "RGBA" or im.getchannel("A").getextrema()[0] > 240
            except Exception: continue
            if not opaque or number in (1,2,19,20): continue
            # Repeated use of an existing source photo shares an explicit key.
            if target not in source_targets:
                image_key = f"image_{len(source_targets)+1}"
                source_targets[target] = image_key
                image_slots[image_key] = {"key": image_key, "first_slide": number, "role": current_role, "section": section, "aspect_ratio": round(display_w/display_h,3), "optional": True, "source_media": target}
            image_key = source_targets[target]
            nv = sh.find(".//p:cNvPr", NS)
            nv.set("name", "{{" + image_key + "}}")
            nv.set("descr", "{{" + image_key + "}}")
            rec["image_keys"].append(image_key)
        new_part = f"ppt/slides/slide{number}.xml"
        new_slides[new_part] = xml(root)
        new_slides[f"ppt/slides/_rels/slide{number}.xml.rels"] = xml(rel)
        rel_id = f"rIdSubjectSlide{number}"
        ET.SubElement(prel, "{" + REL + "}Relationship", Id=rel_id, Type=NS["r"] + "/slide", Target=f"slides/slide{number}.xml")
        ET.SubElement(lst, "{" + NS["p"] + "}sldId", id=str(255+number), attrib={"{" + NS["r"] + "}id": rel_id})
        ET.SubElement(ct, "{" + CT + "}Override", PartName="/"+new_part, ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
        slides.append(rec)
    # Safe to write now: the originals were held separately during duplication.
    parts.update(new_slides)
    parts["ppt/presentation.xml"] = xml(p)
    parts["ppt/_rels/presentation.xml.rels"] = xml(prel)
    parts["[Content_Types].xml"] = xml(ct)
    app = ET.fromstring(parts["docProps/app.xml"])
    for element in app.iter():
        if ET.QName(element).localname == "Slides": element.text = "20"
    parts["docProps/app.xml"] = xml(app)
    rootrels = ET.fromstring(parts["_rels/.rels"])
    for rel in list(rootrels):
        if rel.get("Type", "").endswith("/thumbnail"): rootrels.remove(rel)
    parts["_rels/.rels"] = xml(rootrels)
    parts = prune_parts(parts)
    subset_embedded_fonts(parts)
    compact_images(parts)
    dest = ROOT / subject / f"id_{variant}.pptx"
    write_package(parts, dest)
    optimize_pptx(dest)
    manifest = {"version": 1, "subject": subject, "variant": variant, "label": SUBJECTS[subject]["label"], "source_name": source_name, "source_bytes": len(raw), "template": dest.name, "slide_count": 20, "plan_count": 4, "size_bytes": dest.stat().st_size, "fields": fields, "slides": slides, "image_slots": list(image_slots.values())}
    dest.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(subject, variant, dest.stat().st_size, len(fields), "fields", len(image_slots), "images")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("uploads", type=Path)
    args = ap.parse_args()
    inputs = []
    for arc in args.uploads.glob("*.zip"):
        subject = arc.stem.lower()
        if subject not in SUBJECTS: continue
        with ZipFile(arc) as z:
            for name in sorted(z.namelist()):
                if name.lower().endswith(".pptx"):
                    inputs.append((subject, name, z.read(name)))
    inputs.sort(key=lambda row: (row[0], row[1]))
    if len(inputs) != 11:
        raise ValueError("Expected the 11 designs in fizika, english, cyber, huquq and Geografiya ZIPs")
    counts = {}
    for idx, (subject, name, raw) in enumerate(inputs):
        counts[subject] = counts.get(subject, 0) + 1
        prepare(raw, name, subject, counts[subject], ORDERS[idx])
    for subject, info in SUBJECTS.items():
        folder = ROOT / subject
        (folder/"performance.json").write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (folder/"PERFORMANCE.md").write_text(f"# {info['label']} taqdimot yo‘riqnomasi\n\n{info['guidance']}\n\n## 20 slayd tartibi\n\n1. Mavzu va muallif\n2. To‘rtta reja bandi\n3. Kirish\n4–15. Har reja uchun tushuncha, izoh va misol\n16. Amaliy topshiriq\n17. Xulosa\n18. Savollar va javoblar\n19. Manbalar\n20. Minnatdorchilik\n\n## Mavzuga mos reja yo‘nalishlari\n\n"+"\n".join(f"- {s}" for s in info['sections'])+f"\n\n## Rasmlar\n\n{info['image_rule']}\n\nHar variantning `id_N.json` fayli aniq matn kalitlari, belgilar chegarasi va ixtiyoriy rasm joylarini beradi. Kalit formatini `{{{{kalit}}}}` holatida saqlang. Matn bir nechta PowerPoint runlariga bo‘linsa ham bot uni almashtiradi. Fon, naqsh, dekorativ ikonka, ranglar va o‘lchamlar saqlanadi.\n\nRasmlar shape `name` hamda `descr` bo‘yicha `{{{{image_N}}}}` bilan belgilanadi. `ppt/media/imageN.*` fayl nomini rasm kaliti deb ishlatmang. Rasmlar berilmasa original surat qoladi.\n",encoding="utf-8")


if __name__ == "__main__":
    main()
