"""Prepared subject packs: exact schemas, constraints and prompts."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT = Path(__file__).parent / "pro_templates"
SUBJECTS = (
    "fizika", "english", "cyber", "huquq", "geografiya", "tibbiyot", "tarix",
    "sport", "moliya", "minimalizm", "matematika", "marketing", "bolalar", "kimyo",
    "biologiya", "adabiyot", "bank",
)
ALIASES = {
    "physics": "fizika", "ingliz_tili": "english", "ingliz": "english",
    "kiberxavfsizlik": "cyber", "cybersecurity": "cyber", "law": "huquq",
    "geography": "geografiya", "medicine": "tibbiyot", "medical": "tibbiyot",
    "history": "tarix", "sports": "sport", "finance": "moliya",
    "minimalism": "minimalizm", "minimalist": "minimalizm", "math": "matematika",
    "mathematics": "matematika", "children": "bolalar", "kids": "bolalar",
    "chemistry": "kimyo",
    "biology": "biologiya", "literature": "adabiyot", "banking": "bank",
}

LEGACY_LABELS = {"biologiya": "Biologiya", "adabiyot": "Adabiyot", "bank": "Bank ishi"}


def legacy_manifest(subject, variant):
    """Keep the already supplied biology/literature/banking designs in the single catalog."""
    files = sorted((ROOT / subject).glob('*.pptx'))
    if variant < 1 or variant > len(files):
        raise ValueError(f'{subject} uchun #{variant} variant topilmadi')
    path = files[variant - 1]
    from .schema_20_slayd import FIELD_DESCRIPTIONS, TEXT_LIMITS
    fields, slots, slides = {}, {}, []
    ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
          'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
    with ZipFile(path) as package:
        names = sorted((name for name in package.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', name)),
            key=lambda name: int(re.search(r'slide(\d+)', name).group(1)))
        for number, name in enumerate(names, 1):
            root = etree.fromstring(package.read(name))
            keys = set(re.findall(r'\{\{([^{}]+)\}\}', ''.join(root.xpath('//a:t/text()', namespaces=ns))))
            for key in keys:
                limit = TEXT_LIMITS.get(key, {}).get('max_chars', 450 if key.endswith(('matni', 'asosi', 'sharxi', 'reason')) else 150)
                fields.setdefault(key, {'slide': number, 'kind': 'text', 'role': 'content', 'max_chars': limit,
                    'description': (FIELD_DESCRIPTIONS.get(key, f'Mavzuga mos {key} matni.') if subject == 'biologiya'
                        else f'Mavzuga mos {key} matni.')})
            for value in root.xpath('//p:cNvPr/@name | //p:cNvPr/@descr', namespaces=ns):
                for key in re.findall(r'\{\{(image_\d+)\}\}', value):
                    if key not in {'image_1', 'image_2'}:
                        slots.setdefault(key, {'key': key, 'first_slide': number, 'role': 'content',
                            'aspect_ratio': 1.0, 'optional': True})
            slides.append({'number': number, 'role': 'content', 'section': None, 'text_keys': sorted(keys)})
    if not fields:
        raise ValueError(f'Shablonda matn kalitlari topilmadi: {path.name}')
    plans = [int(match.group(1)) for key in fields if (match := re.fullmatch(r'reja_(\d+)', key))]
    return {'subject': subject, 'variant': variant, 'template': path.name, 'source_name': path.name,
        'slide_count': len(slides), 'plan_count': max(plans or [4]), 'size_bytes': path.stat().st_size,
        'fields': fields, 'image_slots': list(slots.values()), 'slides': slides}


def canonical_subject(subject: str | None) -> str | None:
    if subject is None: return None
    key = subject.strip().lower()
    return ALIASES.get(key, key)


def is_subject_pack(subject: str | None) -> bool:
    return canonical_subject(subject) in SUBJECTS


@lru_cache(maxsize=64)
def load_manifest(subject: str, variant: int = 1) -> dict:
    subject = canonical_subject(subject)
    if subject not in SUBJECTS:
        raise ValueError(f"Bu soha yangi shablon to‘plamiga kirmaydi: {subject}")
    manifest = ROOT / subject / f"id_{variant}.json"
    if not manifest.is_file():
        if subject in LEGACY_LABELS:
            return legacy_manifest(subject, variant)
        raise ValueError(f"{subject} uchun #{variant} variant topilmadi")
    return json.loads(manifest.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def load_performance(subject: str) -> dict:
    if subject in LEGACY_LABELS:
        return {"label": LEGACY_LABELS[subject], "guidance": "Mavzuni ilmiy, tushunarli va izchil tushuntiring. "
            "Manba, raqam, iqtibos va tadqiqot natijasini to‘qimang.",
            "sections": ["Tushuncha", "Asosiy jihatlar", "Tahlil", "Xulosa"],
            "image_rule": "Mavzuga mos suratlarni ixtiyoriy rasm joylariga joylashtiring; bezaklar saqlansin."}
    return json.loads((ROOT / canonical_subject(subject) / "performance.json").read_text(encoding="utf-8"))


def build_subject_schema(subject: str, variant: int, topic: str, author: str) -> dict:
    manifest = load_manifest(subject, variant)
    schema = {}
    for key, field in manifest["fields"].items():
        context = f"Slayd {field['slide']}, vazifa {field.get('role', field['kind'])}. " if field.get("slide") else ""
        if field.get("section"):
            context += f"Rejaning {field['section']}-bandiga tegishli. "
        schema[key] = context + field["description"] + f" Maksimum {field['max_chars']} belgi."
    if 'topic' in schema:
        schema["topic"] += f" To‘liq mavzu: {topic}. Qisqa nom mazmunni saqlasin."
    schema["muallif"] = f"Muallif: {author}. Foydalanuvchi bergan ismni o‘zgartirmang."
    schema["image_keywords"] = [
        f"English search phrase for slide {slot['first_slide']}, {slot['role']}, plan {slot.get('section') or 'general'}, topic {topic}, aspect {slot['aspect_ratio']}."
        for slot in manifest["image_slots"]
    ]
    return schema


def subject_instructions(subject: str, variant: int) -> str:
    info = load_performance(subject)
    manifest = load_manifest(subject, variant)
    sequence = ", ".join(f"{s['number']}:{s['role']}" + (f"/plan{s['section']}" if s['section'] else "") for s in manifest["slides"])
    return (
        info["guidance"] + "\nSuggested section directions (adapt to the actual topic): " + "; ".join(info["sections"])
        + f"\n{manifest['slide_count']}-slide sequence: " + sequence
        + f"\nKeep every title and text within its character limit. No markdown, {{{{tokens}}}}, fake citations, repeated paragraphs or filler. Keep the {manifest['plan_count']} agenda items consistent with their related slides."
        + "\nReferences: list only identifiable real sources or sources supplied by the user. Never invent author names, laws, dates or URLs. With no supplied references, write a short honest label if verified sources are unavailable."
        + "\nVisuals: " + info["image_rule"]
        + f" Return exactly {len(manifest['image_slots'])} image_keywords in the declared order. An illustrated template with no photo slots must return []."
    )


def validate_payload(data: dict, subject: str, variant: int) -> None:
    errors = []
    for key, spec in load_manifest(subject, variant)["fields"].items():
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}: matn yo‘q")
        elif "{{" in value or "}}" in value:
            errors.append(f"{key}: almashtirilmagan kalit")
        elif key != "muallif" and len(value) > spec["max_chars"]:
            errors.append(f"{key}: {len(value)} > {spec['max_chars']} belgi")
    if errors:
        raise ValueError("Shablon ma’lumotlari mos emas: " + "; ".join(errors))


def list_subject_templates() -> list[dict]:
    result = []
    for subject in SUBJECTS:
        variants = []
        manifests = ([load_manifest(subject, i) for i in range(1, len(list((ROOT / subject).glob('*.pptx'))) + 1)]
            if subject in LEGACY_LABELS else [json.loads(path.read_text(encoding='utf-8')) for path in sorted((ROOT / subject).glob('id_*.json'))])
        for manifest in manifests:
            variants.append({"variant": manifest["variant"], "name": manifest["source_name"].removesuffix(".pptx"), "slide_count": manifest["slide_count"], "plan_count": manifest["plan_count"], "size_bytes": manifest["size_bytes"], "image_count": len(manifest["image_slots"])})
        result.append({"subject": subject, "label": load_performance(subject)["label"], "variants": variants})
    return result
