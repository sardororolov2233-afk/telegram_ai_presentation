from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.services import image_generation
from app.services.generation_errors import persisted_error, public_error
from app.services.presentation import image_fetcher
from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.pipeline import PresentationPipeline
from app.services.presentation.subject_templates import load_manifest
from test_integration import login, completed_job


@pytest.mark.parametrize('status,code', [
    (401, 'image_auth_error'), (402, 'image_credit_exhausted'),
    (403, 'image_auth_error'), (404, 'image_model_unavailable'),
    (429, 'image_rate_limit'), (500, 'image_provider_error'),
])
async def test_image_provider_failure_preserves_safe_cause_without_retry(tmp_path, monkeypatch, caplog, status, code):
    calls = []
    secret = 'private-test-provider-key'
    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': secret + ' private prompt'}},
                              headers={'x-request-id': secret})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', secret)
    with pytest.raises(image_generation.ImageGenerationError) as caught:
        await image_generation.generate_image('private prompt', tmp_path / 'result.png')
    assert caught.value.code == code and caught.value.status_code == status
    assert caught.value.request_id is None
    assert secret not in str(caught.value) + caplog.text
    assert 'private prompt' not in str(caught.value) + caplog.text
    assert len(calls) == 1
    assert not (tmp_path / 'result.png').exists()


@pytest.mark.parametrize('body,code', [
    ([], 'image_invalid_response'), ({'data': 'bad shape'}, 'image_invalid_response'),
    ({'data': [{'url': 'https://example.invalid/image'}]}, 'image_invalid_response'),
    ({'data': [{'b64_json': 'not base64!'}]}, 'image_invalid_data'),
])
async def test_invalid_provider_images_are_rejected_safely(tmp_path, monkeypatch, body, code):
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)), **kw))
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', 'test-key')
    with pytest.raises(image_generation.ImageGenerationError) as caught:
        await image_generation.generate_image('An educational visual', tmp_path / 'result.png')
    assert caught.value.code == code
    assert not (tmp_path / 'result.png').exists()


async def test_failed_image_attempts_preserve_cause_and_restart_never_repeats_charge(tmp_path, monkeypatch):
    calls = []
    async def failed(prompt, output):
        calls.append(prompt)
        raise image_generation.ImageGenerationError('image_credit_exhausted', 402)
    monkeypatch.setattr(image_fetcher, 'generate_image', failed)
    with pytest.raises(image_generation.ImageGenerationError) as caught:
        await image_fetcher.fetch_images_for_slides(['one', 'two', 'three', 'four'], cache_dir=tmp_path)
    assert caught.value.code == 'image_credit_exhausted'
    with pytest.raises(RuntimeError):
        await image_fetcher.fetch_images_for_slides(['one', 'two', 'three', 'four'], cache_dir=tmp_path)
    assert len(calls) == 3


async def test_old_pdf_job_checks_converter_before_spending_on_ai(tmp_path, monkeypatch):
    from app.services.presentation import pdf_converter
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setattr(settings, 'JOB_STORAGE_DIR', str(tmp_path))
    monkeypatch.setattr(pdf_converter, 'pdf_available', lambda: False)
    async def forbidden(*args, **kwargs):
        pytest.fail('Unavailable PDF must fail before AI or image generation')
    monkeypatch.setattr(AIContentGenerator, 'generate_template_slides', forbidden)
    with pytest.raises(pdf_converter.PdfUnavailableError):
        await PresentationPipeline().run('Education', document_format='pdf')
    assert not list(tmp_path.iterdir())


def test_persisted_errors_and_legacy_job_messages_are_safe():
    code, message = public_error("[Errno 13] Permission denied: 'libreoffice'")
    assert code == 'pdf_unavailable' and 'PPTX' in message
    assert public_error('Shablon mazmunini tekshirish muvaffaqiyatsiz')[0] == 'presentation_content_invalid'
    error = RuntimeError('private key and arbitrary provider response')
    assert 'private key' not in persisted_error(error)
    assert public_error(persisted_error(error))[0] == 'generation_failed'


def test_image_failure_refunds_credit_and_reports_cause_without_second_provider_request(client, monkeypatch):
    from app.services.presentation import pipeline
    uid = 98100
    headers = login(client, uid)
    client.db.rpc('commerce_register', {'p_user_id': uid + 1, 'p_first_name': 'Friend', 'p_referrer_id': uid}).execute()
    client.db.rpc('commerce_confirm_referral', {'p_user_id': uid + 1}).execute()
    calls = []
    async def content(self, **kwargs):
        return {key: 'Matn' for key in load_manifest('bolalar', 1)['fields']}, ['Educational visual']
    async def unavailable(*args, **kwargs):
        calls.append(True)
        raise image_generation.ImageGenerationError('image_credit_exhausted', 402)
    monkeypatch.setattr(AIContentGenerator, 'generate_template_slides', content)
    monkeypatch.setattr(pipeline, 'fetch_images_for_slides', unavailable)
    request_id = str(uuid4())
    headers['Idempotency-Key'] = request_id
    body = {'topic': 'Education research', 'author': 'Student', 'subject': 'bolalar', 'variant': '1'}
    response = client.post('/api/v1/presentations/generate', headers=headers, data=body)
    assert response.status_code == 202
    job = completed_job(client, headers, request_id)
    assert job['status'] == 'failed' and job['error_code'] == 'image_credit_exhausted'
    assert '402' not in job['message']
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 1
    assert client.post('/api/v1/presentations/generate', headers=headers, data=body).status_code == 202
    assert calls == [True]
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 1
