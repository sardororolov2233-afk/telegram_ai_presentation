import base64
import io
import json
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image
import pytest

from app.core.config import settings
from app.services.design import telegram_sender
from test_integration import login


def png():
    buffer = io.BytesIO()
    Image.new('RGB', (60, 40), 'blue').save(buffer, format='PNG')
    return buffer.getvalue()


def images(tmp_path, count):
    paths = [tmp_path / f'variant_{index}.png' for index in range(count)]
    for path in paths:
        path.write_bytes(png())
    return paths


def mock_telegram(monkeypatch, respond):
    original = httpx.AsyncClient
    monkeypatch.setattr(telegram_sender.httpx, 'AsyncClient',
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', 'test-token-never-log')


def track_uploads(monkeypatch, paths):
    original = Path.open
    handles = []

    def opened(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if self in paths and args == ('rb',):
            handles.append(result)
        return result

    monkeypatch.setattr(Path, 'open', opened)
    return handles


def delivered(count):
    messages = [{'message_id': index + 1} for index in range(count)]
    return httpx.Response(200, json={'ok': True, 'result': messages[0] if count == 1 else messages})


@pytest.mark.parametrize('count', [1, 3])
async def test_design_delivery_requires_confirmed_media_and_closes_uploads(tmp_path, monkeypatch, count):
    paths = images(tmp_path, count)
    handles = track_uploads(monkeypatch, paths)
    requests = []

    def respond(request):
        requests.append(request)
        return delivered(1 if request.url.path.endswith('/sendMessage') else count)

    mock_telegram(monkeypatch, respond)
    description = '<b>A & B</b> <unexpected>'
    assert await telegram_sender.send_design_images(42, paths, description, 'instagram', 'minimalism')
    assert [request.url.path.rsplit('/', 1)[-1] for request in requests] == [
        'sendMessage', 'sendPhoto' if count == 1 else 'sendMediaGroup']
    info = json.loads(requests[0].content)
    assert description in info['text'] and 'parse_mode' not in info
    assert len(handles) == count and all(handle.closed for handle in handles)


@pytest.mark.parametrize('count', [1, 3])
@pytest.mark.parametrize('failure', ['http403', 'ok_false', 'missing_confirmation', 'network'])
async def test_design_delivery_failure_is_false_and_closes_files(tmp_path, monkeypatch, caplog, count, failure):
    paths = images(tmp_path, count)
    handles = track_uploads(monkeypatch, paths)

    def respond(request):
        if request.url.path.endswith('/sendMessage'):
            return delivered(1)
        if failure == 'network':
            raise httpx.ReadTimeout('Do not log https://api.telegram.org/bottest-token-never-log/sendPhoto')
        if failure == 'http403':
            return httpx.Response(403, json={'ok': False, 'description': 'Forbidden'})
        if failure == 'ok_false':
            return httpx.Response(200, json={'ok': False, 'description': 'Rejected'})
        return httpx.Response(200, json={'ok': True, 'result': []})

    mock_telegram(monkeypatch, respond)
    assert not await telegram_sender.send_design_images(42, paths, 'Test design', 'instagram', 'minimalism')
    assert len(handles) == count and all(handle.closed for handle in handles)
    assert all(path.exists() for path in paths)
    assert 'test-token-never-log' not in caplog.text


@pytest.mark.parametrize('failure', ['http403', 'network'])
async def test_info_failure_still_attempts_and_confirms_images(tmp_path, monkeypatch, failure):
    paths = images(tmp_path, 3)
    methods = []

    def respond(request):
        methods.append(request.url.path.rsplit('/', 1)[-1])
        if request.url.path.endswith('/sendMessage'):
            if failure == 'network':
                raise httpx.ConnectError('Connection unavailable')
            return httpx.Response(403, json={'ok': False})
        return delivered(3)

    mock_telegram(monkeypatch, respond)
    assert await telegram_sender.send_design_images(42, paths, 'Test design', 'instagram', 'minimalism')
    assert methods == ['sendMessage', 'sendMediaGroup']


async def test_missing_upload_closes_previously_opened_file(tmp_path, monkeypatch):
    paths = images(tmp_path, 1) + [tmp_path / 'missing.png']
    handles = track_uploads(monkeypatch, paths)
    mock_telegram(monkeypatch, lambda request: delivered(1))
    assert not await telegram_sender.send_design_images(42, paths, 'Test design', 'instagram', 'minimalism')
    assert len(handles) == 1 and handles[0].closed


@pytest.mark.parametrize('failure', ['http403', 'ok_false', 'network'])
def test_design_api_preserves_images_and_spends_generation_credit_when_delivery_fails(
        client, tmp_path, monkeypatch, failure):
    from app.api.v1 import designs

    user_id = 10_000_000_000 + (uuid4().int % 1_000_000_000) * 10
    headers = login(client, user_id)
    client.db.rpc('commerce_register', {'p_user_id': user_id + 1, 'p_referrer_id': user_id}).execute()
    client.db.rpc('commerce_confirm_referral', {'p_user_id': user_id + 1}).execute()
    monkeypatch.setattr(designs, 'STATIC_DIR', str(tmp_path))

    async def render(**kwargs):
        return [path.name for path in images(tmp_path, 3)]

    monkeypatch.setattr(designs, 'run_design_pipeline', render)
    methods = []

    def respond(request):
        methods.append(request.url.path.rsplit('/', 1)[-1])
        if request.url.path.endswith('/sendMessage'):
            return delivered(1)
        if failure == 'network':
            raise httpx.ReadTimeout('Telegram unavailable')
        return httpx.Response(403 if failure == 'http403' else 200, json={'ok': False})

    # The fixture's auth token was issued with its own bot token; only replace transport here.
    original = httpx.AsyncClient
    monkeypatch.setattr(telegram_sender.httpx, 'AsyncClient',
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    headers['Idempotency-Key'] = str(uuid4())
    response = client.post('/api/v1/designs/generate', headers=headers, json={
        'description': '<b>A & B</b> poster', 'format': 'instagram', 'style': 'minimalism',
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['telegram_sent'] is False
    assert len(body['images']) == 3
    assert all(base64.b64decode(image.split(',', 1)[1]) == png() for image in body['images'])
    assert methods == ['sendMessage', 'sendMediaGroup']
    assert client.get('/api/v1/commerce', headers=headers).json()['referral_credits'] == 0
    assert not list(tmp_path.glob('variant_*.png'))
