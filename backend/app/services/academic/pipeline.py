"""Run Orzu's long academic jobs in the existing durable backend worker."""
import asyncio
import re
from pathlib import Path
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field
from app.core.config import settings
from app.services.presentation.telegram_sender import send_document
from .brain import ask_ai, load_prompt
from .course import generate_full_course_work
from .referat_doc import create_referat_document
from .course_doc import create_course_word_document


class AcademicInput(BaseModel):
    tema: str = Field(min_length=3, max_length=500)
    plan: str = Field(min_length=10, max_length=16000)
    til: Literal["O'zbek", 'English', 'Русский', 'Français'] = "O'zbek"
    universitet: str = Field(default='-', max_length=250)
    fakultet: str = Field(default='-', max_length=250)
    muallif: str = Field(min_length=2, max_length=150)
    kurs_guruh: str = Field(default='-', max_length=150)
    sahifa: int = Field(default=15, ge=5, le=100)
    uslub: str = Field(default='Akademik', max_length=100)
    ish_turi: Literal['REFERAT', 'MUSTAQIL ISH', 'KURS ISHI'] = 'REFERAT'


async def generate_referat(data: AcademicInput):
    labels = {
        "O'zbek": ('KIRISH', 'XULOSA', "FOYDALANILGAN ADABIYOTLAR RO'YXATI", ['I BOB', 'II BOB', 'III BOB']),
        'English': ('INTRODUCTION', 'CONCLUSION', 'REFERENCES', ['CHAPTER I', 'CHAPTER II', 'CHAPTER III']),
        'Русский': ('ВВЕДЕНИЕ', 'ЗАКЛЮЧЕНИЕ', 'СПИСОК ЛИТЕРАТУРЫ', ['ГЛАВА I', 'ГЛАВА II', 'ГЛАВА III']),
        'Français': ('INTRODUCTION', 'CONCLUSION', 'BIBLIOGRAPHIE', ['CHAPITRE I', 'CHAPITRE II', 'CHAPITRE III']),
    }[data.til]
    intro, conclusion, references, chapters = labels
    sections = [(intro, 'Explain relevance, aim, tasks and scope. No conclusion.')]
    for index, prefix in enumerate(chapters):
        # Preserve the approved plan's concrete heading, instead of ignoring it.
        heading = next((line.strip() for line in data.plan.splitlines()
            if re.match(r'^' + re.escape(prefix) + r'\b', line.strip(), re.I)), prefix)
        sections.append((heading, 'Give a detailed analytical discussion. Avoid repeating other chapters.'))
    sections.extend([(conclusion, 'Summarize findings and practical suggestions without repeating the introduction.'),
        (references, 'List only sources you can reliably identify. Never invent citations, titles, page numbers or URLs. State any uncertainty.')])
    output = []
    for heading, instruction in sections:
        prompt = load_prompt('referat/11_referat_section.txt', topic=data.tema, plan=data.plan,
            section_name=heading, volume='Detailed academic analysis (approximately 700-1200 words for a body chapter)',
            instructions=instruction + ' Write strictly in ' + data.til + '.', language=data.til)
        text = await ask_ai(prompt)
        if text.upper().startswith(heading.upper()):
            text = text[len(heading):].lstrip(' \n.:-')
        output.append(heading + '\n\n' + text)
    return '\n\n'.join(output)


class AcademicPipeline:
    def __init__(self, service):
        if service not in {'referat', 'course'}:
            raise ValueError('Invalid academic service')
        self.service = service

    async def run(self, telegram_id=None, **payload):
        data = AcademicInput.model_validate(payload)
        if self.service == 'course':
            text = await generate_full_course_work(data.tema, data.plan, data.til)
            writer = create_course_word_document
        else:
            text = await generate_referat(data)
            writer = create_referat_document
        if not text or not text.strip():
            raise ValueError('Academic content is empty')
        directory = Path(settings.JOB_STORAGE_DIR) / 'outputs'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'{self.service}_{uuid4()}.docx'
        try:
            written = await asyncio.to_thread(writer, tema=data.tema, sahifa=data.sahifa, uslub=data.uslub,
                text=text, universitet=data.universitet, fakultet=data.fakultet, muallif=data.muallif,
                kurs_guruh=data.kurs_guruh, doc_type='KURS ISHI' if self.service == 'course' else data.ish_turi,
                plan=data.plan, output_path=str(path))
            if not written or not path.is_file():
                raise ValueError('Document rendering failed')
            sent = await send_document(telegram_id, str(path), '📄 ' + data.tema[:900]) if telegram_id else False
            return {'document_path': str(path), 'telegram_sent': sent}
        except BaseException:
            path.unlink(missing_ok=True)
            raise
