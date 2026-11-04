import io
import json
from pathlib import Path
from uuid import uuid4

from docx import Document
import httpx
import pytest

from app.core.config import settings
from app.services.article import pipeline, telegram_sender
from test_integration import login, completed_job


@pytest.fixture
def article(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'JOB_STORAGE_DIR', str(tmp_path))
    content = {'title': 'Teacher communication', 'abstract': 'An academic abstract. ' * 8,
        'keywords': ['teacher', 'communication', 'education'],
        'sections': [{'heading': name, 'paragraphs': ['Academic discussion. ' * 5]}
                     for name in ['Introduction', 'Methodology', 'Discussion']],
        'conclusion': 'An academic conclusion. ' * 8, 'references': []}
    async def generate(self, *args):
        return json.dumps(content)
    monkeypatch.setattr(pipeline.ArticlePipeline, '_call_llm', generate)
    return pipeline.ArticlePipeline()


async def test_article_document_is_delivered_before_separate_publication_offer(article, monkeypatch):
    events = []
    async def document(user_id, path, caption):
        assert Path(path).is_file()
        assert '@tammaddunuz' not in caption
        events.append(('document', user_id))
        return True
    async def offer(user_id):
        events.append(('offer', user_id))
        return True
    monkeypatch.setattr(pipeline, 'send_document', document)
    monkeypatch.setattr(pipeline, 'send_publication_offer', offer)
    result = await article.run('Teacher communication', 'Ergasheva Sarvinoz', 'uz', 123)
    assert events == [('document', 123), ('offer', 123)]
    assert result['telegram_sent'] is True
    word = Document(result['document_path'])
    text = '\n'.join(paragraph.text for paragraph in word.paragraphs)
    assert 'Ergasheva Sarvinoz' in text and 'Methodology' in text
    assert '@tammaddunuz' not in text


@pytest.mark.parametrize('telegram_id,delivered', [(None, True), (123, False)])
async def test_no_offer_when_article_is_not_sent_to_telegram(article, monkeypatch, telegram_id, delivered):
    calls = []
    async def document(*args):
        calls.append('document')
        return delivered
    async def offer(*args):
        pytest.fail('An undelivered article must not trigger a publication offer')
    monkeypatch.setattr(pipeline, 'send_document', document)
    monkeypatch.setattr(pipeline, 'send_publication_offer', offer)
    result = await article.run('Teacher communication', 'Student', 'uz', telegram_id)
    assert result['telegram_sent'] is False
    assert Path(result['document_path']).is_file()
    assert calls == ([] if telegram_id is None else ['document'])


@pytest.mark.parametrize('stage', ['generation', 'rendering', 'delivery'])
async def test_failed_article_never_sends_offer(article, monkeypatch, stage):
    calls = []
    async def offer(*args):
        calls.append('offer')
    async def document(*args):
        if stage == 'delivery':
            raise RuntimeError('Telegram unavailable')
        return True
    if stage == 'generation':
        async def invalid(self, *args):
            return 'invalid JSON'
        monkeypatch.setattr(pipeline.ArticlePipeline, '_call_llm', invalid)
    elif stage == 'rendering':
        def failed(*args):
            raise RuntimeError('Document rendering failed')
        monkeypatch.setattr(pipeline.ArticlePipeline, 'write_document', failed)
    monkeypatch.setattr(pipeline, 'send_document', document)
    monkeypatch.setattr(pipeline, 'send_publication_offer', offer)
    with pytest.raises((ValueError, RuntimeError)):
        await article.run('Teacher communication', 'Student', 'uz', 123)
    assert calls == []
    assert not list(Path(settings.JOB_STORAGE_DIR).rglob('*.docx'))


@pytest.mark.parametrize('raises', [False, True])
async def test_offer_failure_keeps_delivered_article_and_original_result(article, monkeypatch, raises):
    async def document(*args):
        return True
    async def offer(*args):
        if raises:
            raise RuntimeError('Unexpected marketing transport failure')
        return False
    monkeypatch.setattr(pipeline, 'send_document', document)
    monkeypatch.setattr(pipeline, 'send_publication_offer', offer)
    result = await article.run('Teacher communication', 'Student', 'uz', 123)
    assert result['telegram_sent'] is True
    assert Path(result['document_path']).is_file()
    assert Document(result['document_path']).paragraphs
    assert set(result) == {'document_path', 'telegram_sent'}


@pytest.mark.parametrize('case,expected', [
    ('success', True), ('rejected', False), ('http_error', False),
    ('invalid_json', False), ('invalid_shape', False), ('network', False),
])
async def test_offer_sender_sends_exact_html_message_and_handles_failure(monkeypatch, caplog, case, expected):
    token = '123456:private-test-token'
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', token)
    requests = []
    def respond(request):
        requests.append(request)
        if case == 'network':
            raise httpx.ConnectError('Unavailable ' + str(request.url), request=request)
        if case == 'http_error':
            return httpx.Response(429, json={'ok': False, 'parameters': {'retry_after': 20}})
        if case == 'invalid_json':
            return httpx.Response(200, content=b'not JSON')
        if case == 'invalid_shape':
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={'ok': case == 'success'})
    original = httpx.AsyncClient
    monkeypatch.setattr(telegram_sender.httpx, 'AsyncClient',
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    assert await telegram_sender.send_publication_offer(123) is expected
    assert len(requests) == 1
    assert requests[0].method == 'POST'
    assert requests[0].url.path.endswith('/sendMessage')
    body = json.loads(requests[0].content)
    assert body == {'chat_id': 123, 'text': telegram_sender.PUBLICATION_OFFER_TEXT, 'parse_mode': 'HTML'}
    assert 'Tamaddun' in body['text'] and '@tammaddunuz' in body['text']
    assert '80 ming' in body['text'] and 'SERTIFIKAT' in body['text']
    assert '<b>' in body['text'] and '</b>' in body['text']
    assert token not in caplog.text


@pytest.mark.parametrize('telegram_id,token', [(None, 'test-token'), (123, '')])
async def test_missing_telegram_destination_or_token_does_not_make_request(monkeypatch, telegram_id, token):
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', token)
    def forbidden(*args, **kwargs):
        pytest.fail('Missing destination/token must not create a Telegram HTTP client')
    monkeypatch.setattr(telegram_sender.httpx, 'AsyncClient', forbidden)
    assert await telegram_sender.send_publication_offer(telegram_id) is False


@pytest.mark.parametrize('offer_raises', [False, True])
def test_offer_failure_does_not_refund_article_or_remove_download_and_retry_does_not_resend(client, monkeypatch, offer_raises):
    uid = 97002 if offer_raises else 97000
    headers = login(client, uid)
    requests = []
    async def delivered(*args):
        requests.append('document')
        return True
    async def offer(*args):
        requests.append('offer')
        if offer_raises:
            raise RuntimeError('Unexpected marketing transport failure')
        return False
    monkeypatch.setattr(pipeline, 'send_document', delivered)
    monkeypatch.setattr(pipeline, 'send_publication_offer', offer)
    initial = client.get('/api/v1/commerce', headers=headers).json()['standard_free_remaining']
    request_id = str(uuid4())
    headers['Idempotency-Key'] = request_id
    body = {'topic': 'Teacher communication', 'author': 'Student', 'language': 'uz'}
    response = client.post('/api/v1/articles/generate', headers=headers, data=body)
    assert response.status_code == 202, response.text
    job = completed_job(client, headers, request_id)
    assert job['status'] == 'completed' and job['telegram_sent'] is True
    downloaded = client.get(job['download_url'], headers=headers)
    assert downloaded.status_code == 200
    assert Document(io.BytesIO(downloaded.content)).paragraphs
    assert client.get('/api/v1/commerce', headers=headers).json()['standard_free_remaining'] == initial - 1
    repeated = client.post('/api/v1/articles/generate', headers=headers, data=body)
    assert repeated.status_code == 202
    assert completed_job(client, headers, request_id)['status'] == 'completed'
    assert requests == ['document', 'offer']
    other = login(client, uid + 1)
    assert client.get(job['download_url'], headers=other).status_code == 404
