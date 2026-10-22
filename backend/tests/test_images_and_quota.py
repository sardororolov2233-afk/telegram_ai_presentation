import asyncio
import base64
import io
import json
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import httpx
from PIL import Image
import pytest
from app.core.config import settings
from app.services import image_generation
from app.services.presentation import image_fetcher
from app.services.presentation.subject_templates import load_manifest, build_subject_schema
from app.services.presentation.pptx_generator import generate_template_pptx
from test_integration import login


def png(color='red'):
    buffer = io.BytesIO()
    Image.new('RGB', (60, 40), color).save(buffer, format='PNG')
    return buffer.getvalue()


async def test_seedream_api_contract_and_validated_png(tmp_path, monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(png()).decode(), 'media_type': 'image/png'}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(image_generation.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', 'test-key')
    output = tmp_path / 'image.png'
    await image_generation.generate_image('A Silk Road caravan', output, '16:9')
    payload = json.loads(requests[0].content)
    assert requests[0].url.path == '/api/v1/images'
    assert payload == {'model': 'bytedance-seed/seedream-5-0-flash', 'prompt': 'A Silk Road caravan',
        'n': 1, 'resolution': '1K', 'aspect_ratio': '16:9'}
    with Image.open(output) as picture:
        assert picture.format == 'PNG' and picture.size == (60, 40)


async def test_all_backend_text_requests_use_haiku(monkeypatch):
    from app.services.presentation.ai_generator import AIContentGenerator
    from app.services.article.pipeline import ArticlePipeline
    from app.services.design.prompt_enhancer import enhance_prompt
    requests = []
    manifest = load_manifest('tarix', 1)
    content = {key: 'Matn' for key in manifest['fields']}
    content['image_keywords'] = ['Silk Road caravan', 'Historical city', 'Trade route']
    def respond(request):
        requests.append(json.loads(request.content))
        text = json.dumps(content) if len(requests) == 1 else 'Academic text or visual prompt'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': text}}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', 'test-key')
    await AIContentGenerator().generate_template_slides('Silk Road', 'Student', 'uz', 4, subject='tarix')
    await ArticlePipeline()._call_llm('Academic writer', 'Write an article')
    await enhance_prompt('Conference poster', 'instagram', 'minimalism')
    assert len(requests) == 3
    assert {request['model'] for request in requests} == {'anthropic/claude-haiku-5.5'}


async def test_maximum_three_requests_survives_restart_and_fills_template(tmp_path, monkeypatch):
    calls = []
    async def generate(prompt, output):
        calls.append(prompt)
        output.write_bytes(png(['red', 'green', 'blue'][len(calls) - 1]))
    monkeypatch.setattr(image_fetcher, 'generate_image', generate)
    keywords = [f'Historical illustration {i}' for i in range(12)]
    pool = await image_fetcher.fetch_images_for_slides(keywords, cache_dir=tmp_path / 'cache')
    assert len(calls) == len(pool) == 3
    assert await image_fetcher.fetch_images_for_slides(keywords, cache_dir=tmp_path / 'cache') == pool
    assert len(calls) == 3
    manifest = load_manifest('tarix', 1)
    assert len(manifest['image_slots']) > 3
    assert len(build_subject_schema('tarix', 1, 'Silk Road', 'Student')['image_keywords']) == 3
    images = image_fetcher.reuse_images(pool, len(manifest['image_slots']))
    assert len(images) == len(manifest['image_slots']) and len(set(images)) == 3
    content = {key: 'Matn' for key in manifest['fields']}
    output = tmp_path / 'presentation.pptx'
    await generate_template_pptx(content, str(output), user_images=images, subject='tarix', variant=1)
    with ZipFile(output) as package:
        slides = [package.read(name) for name in package.namelist() if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
        assert sum(slide.count(b'rIdBotImage') for slide in slides) >= len(manifest['image_slots'])


async def test_cancelled_or_failed_request_does_not_create_fourth_image(tmp_path, monkeypatch):
    calls = []
    async def generate(prompt, output):
        calls.append(prompt)
        if len(calls) == 1:
            raise asyncio.CancelledError()
        output.write_bytes(png())
    monkeypatch.setattr(image_fetcher, 'generate_image', generate)
    with pytest.raises(asyncio.CancelledError):
        await image_fetcher.fetch_images_for_slides(['one', 'two', 'three', 'four'], cache_dir=tmp_path)
    assert len(await image_fetcher.fetch_images_for_slides(['one', 'two', 'three', 'four'], cache_dir=tmp_path)) == 2
    assert len(calls) == 3
    await image_fetcher.fetch_images_for_slides(['one', 'two', 'three'], cache_dir=tmp_path)
    assert len(calls) == 3


def test_free_article_and_miniapp_available_without_referrals(client):
    headers = login(client, 92000)
    account = client.get('/api/v1/commerce', headers=headers).json()
    assert account['referral_credits'] == 0
    assert account['quotes']['article']['allowed'] is True
    assert account['quotes']['referat']['required_credits'] == 0
    assert account['quotes']['obyektivka']['allowed'] is True
    assert account['quotes']['design']['allowed'] is False
    assert client.get('/miniapp').status_code == 200
    assert client.get('/static/miniapp.js').status_code == 200
    assert 'Obuna sotib olish' not in client.get('/miniapp').text
    headers['Idempotency-Key'] = str(uuid4())
    response = client.post('/api/v1/articles/generate', headers=headers,
        data={'topic': 'History of education', 'author': 'Student', 'language': 'uz'})
    assert response.status_code == 202, response.text
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 0


def test_design_consumes_one_credit_and_failure_returns_it(client, tmp_path, monkeypatch):
    from app.api.v1 import designs
    headers = login(client, 93000)
    body = {'description': 'Educational event poster', 'format': 'instagram', 'style': 'minimalism', 'send_to_telegram': False}
    assert client.post('/api/v1/designs/generate', headers=headers, json=body).status_code == 402
    for friend in [93001, 93002]:
        client.db.rpc('commerce_register', {'p_user_id': friend, 'p_referrer_id': 93000}).execute()
        client.db.rpc('commerce_confirm_referral', {'p_user_id': friend}).execute()
    monkeypatch.setattr(designs, 'STATIC_DIR', str(tmp_path))
    generated = []
    async def render(**kwargs):
        generated.append(kwargs)
        (tmp_path / 'result.png').write_bytes(png())
        return ['result.png']
    monkeypatch.setattr(designs, 'run_design_pipeline', render)
    headers['Idempotency-Key'] = str(uuid4())
    response = client.post('/api/v1/designs/generate', headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['images'][0].startswith('data:image/png;base64,')
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 1
    assert client.post('/api/v1/designs/generate', headers=headers, json=body).status_code == 409
    assert len(generated) == 1
    async def failed(**kwargs): raise RuntimeError('Seedream unavailable')
    monkeypatch.setattr(designs, 'run_design_pipeline', failed)
    headers['Idempotency-Key'] = str(uuid4())
    assert client.post('/api/v1/designs/generate', headers=headers, json=body).status_code == 500
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 1
