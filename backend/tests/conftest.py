import json
import shutil
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
TEST_TOKEN = '123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'


@pytest.fixture(scope='session')
def sql_server():
    if not shutil.which('node') or not (ROOT / 'node_modules/@electric-sql/pglite').exists():
        pytest.skip('Run npm ci in backend/ to enable PostgreSQL integration tests')
    process = subprocess.Popen(['node', 'tests/support/sql_test_server.mjs'], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = process.stdout.readline()
    if not line.startswith('READY '):
        process.terminate()
        raise RuntimeError(process.stderr.read())
    url = 'http://127.0.0.1:' + line.strip().split()[1]
    yield url
    process.terminate()
    process.communicate(timeout=10)


@pytest.fixture
def client(sql_server, tmp_path, monkeypatch):
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.delenv(name, raising=False)
    from app.core.config import settings
    from app.core import database
    from app.main import app
    from app.services.presentation import pipeline
    from app.services.presentation.ai_generator import AIContentGenerator
    from app.services.presentation.subject_templates import load_manifest
    from app.services.article.pipeline import ArticlePipeline

    values = dict(SUPABASE_URL=sql_server, SUPABASE_KEY='test-service-key', DEBUG=False,
        TELEGRAM_BOT_TOKEN=TEST_TOKEN, TELEGRAM_BOT_USERNAME='orzu_test_bot',
        OPENROUTER_API_KEY='test-key', SECRET_KEY='a-test-secret-with-more-than-32-characters',
        JOB_STORAGE_DIR=str(tmp_path / 'jobs'), JOB_WORKERS=1)
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    db = create_client(sql_server, 'test-service-key')
    monkeypatch.setattr(database, '_supabase', db)

    async def template_content(self, **kwargs):
        fields = load_manifest(kwargs['subject'], kwargs['variant'])['fields']
        content = {key: 'Matn' for key in fields}
        content['muallif'] = kwargs['author'] or 'Test Author'
        return content, []

    async def no_images(keywords, **kwargs):
        return []

    async def delivered(*args, **kwargs):
        return True

    async def article_content(self, *args):
        return json.dumps({'title': 'History research', 'abstract': 'Academic abstract. ' * 10,
            'keywords': ['history', 'education', 'research'],
            'sections': [{'heading': title, 'paragraphs': ['Academic discussion. ' * 30]}
                for title in ['Introduction', 'Methodology', 'Discussion']],
            'conclusion': 'Academic conclusion. ' * 10, 'references': []})

    monkeypatch.setattr(AIContentGenerator, 'generate_template_slides', template_content)
    monkeypatch.setattr(pipeline, 'fetch_images_for_slides', no_images)
    monkeypatch.setattr(pipeline, 'send_presentation_to_telegram', delivered)
    monkeypatch.setattr(ArticlePipeline, '_call_llm', article_content)
    monkeypatch.setattr('app.services.article.pipeline.send_document', delivered)
    monkeypatch.setattr('app.services.job_worker.send_status_message', delivered)
    with TestClient(app) as api:
        api.db = db
        yield api
