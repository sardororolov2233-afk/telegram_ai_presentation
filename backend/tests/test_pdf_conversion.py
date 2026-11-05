from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.api.v1 import presentations
from app.services.presentation import pdf_converter as converter
from test_integration import login, completed_job

PDF = b'%PDF-1.4\nA newly converted document\n%%EOF\n'


@pytest.fixture
def executable(tmp_path, monkeypatch):
    binary = tmp_path / 'working-soffice'
    binary.write_text(f'#!{sys.executable}\n' + '''
from pathlib import Path
import sys
out = Path(sys.argv[sys.argv.index('--outdir') + 1])
source = Path(sys.argv[-1])
(out / (source.stem + '.pdf')).write_bytes(b'%PDF-1.4\\nA newly converted document\\n%%EOF\\n')
''')
    binary.chmod(0o700)
    monkeypatch.setattr(settings, 'LIBREOFFICE_PATH', str(binary))
    return binary


def test_binary_discovery_skips_inaccessible_candidate_and_finds_soffice(tmp_path, monkeypatch):
    inaccessible = tmp_path / 'libreoffice'
    inaccessible.write_text('not executable')
    inaccessible.chmod(0o600)
    executable = tmp_path / 'soffice'
    executable.write_text('executable')
    executable.chmod(0o700)
    monkeypatch.setattr(settings, 'LIBREOFFICE_PATH', '')
    monkeypatch.setattr(converter.shutil, 'which', lambda name: str(inaccessible if name == 'libreoffice' else executable))
    assert converter.libreoffice_binary() == str(executable.resolve())
    assert converter.pdf_available()
    # A mistaken explicit override is not silently replaced by a different binary.
    monkeypatch.setattr(settings, 'LIBREOFFICE_PATH', str(inaccessible))
    assert converter.libreoffice_binary() is None
    assert not converter.pdf_available()
    monkeypatch.setattr(settings, 'LIBREOFFICE_PATH', str(tmp_path))
    assert not converter.pdf_available()


def test_missing_converter_does_not_attempt_bare_path_subprocess(tmp_path, monkeypatch):
    source = tmp_path / 'deck.pptx'
    source.write_bytes(b'original presentation')
    monkeypatch.setattr(settings, 'LIBREOFFICE_PATH', '')
    monkeypatch.setattr(converter.shutil, 'which', lambda name: None)
    def forbidden(*args, **kwargs):
        pytest.fail('An unavailable converter must not reach subprocess execution')
    monkeypatch.setattr(converter.subprocess, 'run', forbidden)
    with pytest.raises(converter.PdfUnavailableError, match='PPTX'):
        converter.convert_pptx_to_pdf(str(source))
    assert source.read_bytes() == b'original presentation'


def test_conversion_uses_fresh_output_separate_profiles_and_atomic_destination(tmp_path, monkeypatch, executable):
    source = tmp_path / 'deck.pptx'
    source.write_bytes(b'original presentation')
    destination = source.with_suffix('.pdf')
    destination.write_bytes(b'old PDF must be replaced')
    calls = []
    original = subprocess.run
    def capture(args, **kwargs):
        calls.append(args)
        assert Path(args[0]).is_absolute()
        assert Path(args[args.index('--outdir') + 1]) != source.parent
        return original(args, **kwargs)
    monkeypatch.setattr(converter.subprocess, 'run', capture)
    assert converter.convert_pptx_to_pdf(str(source)) == str(destination)
    assert destination.read_bytes() == PDF
    assert converter.convert_pptx_to_pdf(str(source)) == str(destination)
    assert calls[0][1] != calls[1][1]
    assert calls[0][1].startswith('-env:UserInstallation=file:')
    assert source.read_bytes() == b'original presentation'
    assert not list(tmp_path.glob('.orzu-pdf-*'))


@pytest.mark.parametrize('new_output', [None, b'<html>converter error</html>', b'%PDF-1.4\ntruncated output'])
def test_old_pdf_never_masks_missing_or_corrupt_new_conversion(tmp_path, monkeypatch, executable, new_output):
    source = tmp_path / 'deck.pptx'
    source.write_bytes(b'original')
    destination = source.with_suffix('.pdf')
    destination.write_bytes(PDF)
    def no_valid_output(args, **kwargs):
        if new_output is not None:
            output = Path(args[args.index('--outdir') + 1]) / 'deck.pdf'
            output.write_bytes(new_output)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(converter.subprocess, 'run', no_valid_output)
    with pytest.raises(converter.PdfConversionError, match='Yangi PDF'):
        converter.convert_pptx_to_pdf(str(source))
    assert destination.read_bytes() == PDF
    assert source.read_bytes() == b'original'
    assert not list(tmp_path.glob('.orzu-pdf-*'))


@pytest.mark.parametrize('failure', ['timeout', 'permission', 'nonzero'])
def test_conversion_failure_is_clear_and_cleans_temporary_files(tmp_path, monkeypatch, executable, failure):
    source = tmp_path / 'deck.pptx'
    source.write_bytes(b'original')
    def fail(args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(args, timeout=120)
        if failure == 'permission':
            raise PermissionError(13, 'permission denied', 'libreoffice')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(converter.subprocess, 'run', fail)
    expected = converter.PdfUnavailableError if failure == 'permission' else converter.PdfConversionError
    with pytest.raises(expected) as error:
        converter.convert_pptx_to_pdf(str(source))
    assert 'libreoffice' not in str(error.value)
    assert source.read_bytes() == b'original'
    assert not source.with_suffix('.pdf').exists()
    assert not list(tmp_path.glob('.orzu-pdf-*'))


@pytest.mark.parametrize('available', [False, True])
def test_public_capabilities_describe_formats_without_server_paths(monkeypatch, available):
    monkeypatch.setattr(presentations, 'pdf_available', lambda: available)
    app = FastAPI()
    app.include_router(presentations.router, prefix='/api/v1')
    with TestClient(app) as client:
        response = client.get('/api/v1/presentations/capabilities')
    assert response.status_code == 200
    assert response.json() == {'pdf_available': available, 'formats': ['ppt', 'pdf'] if available else ['ppt']}


def test_unavailable_pdf_never_reserves_quota_and_pptx_still_works(client, monkeypatch):
    monkeypatch.setattr(presentations, 'pdf_available', lambda: False)
    uid = 98500
    headers = login(client, uid)
    client.db.rpc('commerce_register', {'p_user_id': uid + 1, 'p_referrer_id': uid}).execute()
    client.db.rpc('commerce_confirm_referral', {'p_user_id': uid + 1}).execute()
    before = client.get('/api/v1/commerce', headers=headers).json()['referral_credits']
    assert before == 1
    request_id = str(uuid4())
    headers['Idempotency-Key'] = request_id
    body = {'topic': 'Teacher communication', 'author': 'Student', 'subject': 'minimalizm', 'document_format': 'pdf'}
    uploads = Path(settings.JOB_STORAGE_DIR) / 'uploads'
    rejected = client.post('/api/v1/presentations/generate', headers=headers, data=body)
    assert rejected.status_code == 503
    assert rejected.json()['detail']['code'] == 'pdf_unavailable'
    assert not uploads.exists()
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == before
    assert client.get('/api/v1/jobs/' + request_id, headers=headers).status_code == 404
    queued = client.post('/api/v1/presentations/generate', headers=headers, data={**body, 'document_format': 'ppt'})
    assert queued.status_code == 202, queued.text
    assert completed_job(client, headers, request_id)['status'] == 'completed'
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == before - 1
