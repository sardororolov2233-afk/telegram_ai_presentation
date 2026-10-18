from pathlib import Path
import pytest
from docx import Document
from app.services.academic.pipeline import AcademicPipeline, generate_referat, AcademicInput
from app.core.config import settings


@pytest.mark.asyncio
@pytest.mark.parametrize('service', ['course', 'referat'])
async def test_academic_pipeline_renders_real_docx_with_original_cover(service, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'JOB_STORAGE_DIR', str(tmp_path))
    calls = []

    async def fake_ai(prompt):
        calls.append(prompt)
        return 'Academic analysis with enough detail to form a paragraph. ' * 40

    async def delivered(*args):
        return True

    monkeypatch.setattr('app.services.academic.pipeline.ask_ai', fake_ai)
    monkeypatch.setattr('app.services.academic.course.ai_request', fake_ai)
    monkeypatch.setattr('app.services.academic.pipeline.send_document', delivered)
    plan = 'REJA\nKIRISH\nI BOB: Kushonlar tarixi\n1.1. Nazariy asoslar\n1.2. Tarix\nII BOB: Amaliyot\n2.1. Tahlil\n2.2. Natijalar\nIII BOB: Takliflar\nXULOSA\nADABIYOTLAR'
    result = await AcademicPipeline(service).run(telegram_id=123, tema='Kushonlar tarixi', plan=plan,
        muallif='Sardor Orolov', universitet='Test University', fakultet='History', kurs_guruh='4-kurs',
        sahifa=30, ish_turi='KURS ISHI' if service == 'course' else 'REFERAT')
    path = Path(result['document_path'])
    assert path.is_relative_to(tmp_path / 'outputs')
    assert path.is_file() and result['telegram_sent']
    doc = Document(path)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'Sardor Orolov' in text
    assert 'TEST UNIVERSITY' in text
    assert 'Kushonlar tarixi' in text
    assert len(calls) >= 6
    assert 'Academic analysis' in text
    assert doc.sections[0].left_margin.mm == pytest.approx(30, abs=0.01)


@pytest.mark.asyncio
async def test_failed_delivery_retains_file_for_owned_job_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'JOB_STORAGE_DIR', str(tmp_path))

    async def fake_text(*args):
        return 'KIRISH\nReliable academic text.\nXULOSA\nFindings.'

    async def not_delivered(*args):
        return False

    monkeypatch.setattr('app.services.academic.pipeline.generate_referat', fake_text)
    monkeypatch.setattr('app.services.academic.pipeline.send_document', not_delivered)
    result = await AcademicPipeline('referat').run(telegram_id=123, tema='History topic',
        plan='REJA\nKIRISH\nI BOB\nXULOSA', muallif='Test Author')
    assert Path(result['document_path']).is_file()
    assert not result['telegram_sent']


@pytest.mark.asyncio
async def test_generation_failure_cannot_leave_a_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'JOB_STORAGE_DIR', str(tmp_path))

    async def fail(*args):
        raise RuntimeError('AI unavailable')

    monkeypatch.setattr('app.services.academic.pipeline.generate_referat', fail)
    with pytest.raises(RuntimeError):
        await AcademicPipeline('referat').run(telegram_id=123, tema='History topic',
            plan='REJA\nKIRISH\nI BOB\nXULOSA', muallif='Test Author')
    assert not list(tmp_path.rglob('*.docx'))
