import asyncio
import hashlib
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.api.v1 import broadcasts as routes
from app.services import broadcasts as service


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for name, value in {'JOB_STORAGE_DIR': str(tmp_path), 'BROADCAST_STORAGE_DIR': str(tmp_path), 'ADMIN_ID': '42',
                        'SUPABASE_KEY': 'test-service-key', 'TELEGRAM_BOT_TOKEN': 'test-token'}.items():
        monkeypatch.setattr(settings, name, value)
    return tmp_path


class Clock:
    def __init__(self):
        self.now = 1000.0

    async def sleep(self, seconds):
        self.now += seconds
        await asyncio.sleep(0)


class Users:
    def __init__(self, users):
        self.users = users
        self.pages = []

    async def page(self, job):
        self.pages.append(job['cursor'])
        return [user for user in self.users if job['cursor'] < user <= job['upper_id']][:service.PAGE_SIZE]


class Telegram:
    def __init__(self, clock, failures=None):
        self.clock = clock
        self.failures = failures or {}
        self.calls, self.reports = [], []

    async def copy(self, job, recipient):
        self.calls.append((recipient, self.clock.now))
        errors = self.failures.get(recipient, [])
        if errors:
            raise errors.pop(0)

    async def report(self, job):
        self.reports.append(job)


def setup_worker(users, failures=None):
    store = service.Store()
    data = {'id': '42_101', 'admin_id': 42, 'chat_id': 42, 'message_id': 101}
    store.create(data, '2026-11-04T00:00:00Z', max(users, default=0), len(users))
    clock = Clock()
    telegram = Telegram(clock, failures)
    source = Users(users)
    limiter = service.Limiter(rate=25, clock=lambda: clock.now, sleep=clock.sleep)
    return store, source, telegram, service.Worker(store, source, telegram, limiter)


def run(coroutine):
    return asyncio.run(coroutine)


def test_more_than_fifteen_are_automatic_paged_and_reported_once(environment, monkeypatch):
    monkeypatch.setattr(service, 'PAGE_SIZE', 17)
    store, users, telegram, worker = setup_worker(list(range(1, 104)))
    run(worker.tick())
    job = store.get('42_101')
    assert (job['status'], job['sent'], job['failed']) == ('completed', 103, 0)
    assert [recipient for recipient, _ in telegram.calls] == list(range(1, 104))
    assert len(users.pages) > 5
    assert len(telegram.reports) == 1
    run(worker.tick())
    assert len(telegram.calls) == 103
    assert len(telegram.reports) == 1


def test_restart_skips_successes_even_when_page_cursor_was_not_committed(environment):
    store, users, telegram, worker = setup_worker(list(range(1, 31)))
    store.page('42_101', list(range(1, 31)))
    store.result('42_101', 1, 'sent')
    store.result('42_101', 2, 'sent')
    store.change('42_101', 'running')
    worker.store = service.Store(environment)
    run(worker.tick())
    assert [recipient for recipient, _ in telegram.calls] == list(range(3, 31))
    assert worker.store.get('42_101')['sent'] == 30


def test_429_retries_same_recipient_and_global_cooldown_is_durable(environment, monkeypatch):
    monkeypatch.setattr(service, 'CONCURRENCY', 1)
    failure = service.TelegramFailure(429, parameters={'retry_after': 7})
    store, users, telegram, worker = setup_worker([1, 2, 3], {1: [failure]})
    run(worker.tick())
    assert [recipient for recipient, _ in telegram.calls] == [1, 1, 2, 3]
    assert telegram.calls[1][1] - telegram.calls[0][1] >= 7
    assert store.get('42_101')['sent'] == 3
    # A restart during a persisted flood wait must preserve the pause.
    store, users, telegram, worker = setup_new_campaign_after_completed([4, 5])
    store.cooldown('42_102', 1100)
    worker.store = service.Store(environment)
    run(worker.tick())
    assert telegram.calls[0][1] >= 1100


def setup_new_campaign_after_completed(users):
    store = service.Store()
    store.create({'id': '42_102', 'admin_id': 42, 'chat_id': 42, 'message_id': 102},
                 '2026-11-04T00:00:00Z', max(users), len(users))
    clock = Clock()
    telegram = Telegram(clock)
    source = Users(users)
    return store, source, telegram, service.Worker(store, source, telegram,
        service.Limiter(rate=25, clock=lambda: clock.now, sleep=clock.sleep))


def test_blocked_recipient_fails_only_itself_but_source_failure_pauses_campaign(environment):
    blocked = service.TelegramFailure(403, 'Forbidden: bot was blocked by the user')
    store, users, telegram, worker = setup_worker(list(range(1, 20)), {1: [blocked]})
    run(worker.tick())
    assert (store.get('42_101')['sent'], store.get('42_101')['failed']) == (18, 1)
    store, users, telegram, worker = setup_new_campaign_after_completed([20, 21])
    telegram.failures[20] = [service.TelegramFailure(400, 'Bad Request: message to copy not found')]
    run(worker.tick())
    assert store.get('42_102')['status'] == 'paused'
    assert store.get('42_102')['last_error'] == 'source_unavailable'
    assert store.get('42_102')['failed'] == 0


def test_persistent_transport_failure_pauses_and_does_not_skip_recipient(environment):
    failures = [service.TelegramFailure(503) for _ in range(4)]
    store, users, telegram, worker = setup_worker([1], {1: failures})
    run(worker.tick())
    assert store.get('42_101')['status'] == 'paused'
    assert store.get('42_101')['sent'] == store.get('42_101')['failed'] == 0
    assert len(telegram.calls) == 4
    store.change('42_101', 'queued')
    run(worker.tick())
    assert store.get('42_101')['status'] == 'completed'
    assert store.get('42_101')['sent'] == 1


def test_cancel_stops_pending_recipients(environment):
    store, users, telegram, worker = setup_worker(list(range(1, 100)))
    original = telegram.copy
    async def cancel_after_first(job, recipient):
        await original(job, recipient)
        store.change(job['id'], 'cancelled')
    telegram.copy = cancel_after_first
    run(worker.tick())
    assert store.get('42_101')['status'] == 'cancelled'
    assert len(telegram.calls) == 1
    run(worker.tick())
    assert len(telegram.calls) == 1


def test_worker_flock_allows_only_one_sender(environment):
    with service.worker_lock(environment) as first:
        assert first
        with service.worker_lock(environment) as second:
            assert not second
    with service.worker_lock(environment) as after_shutdown:
        assert after_shutdown


def test_limiter_never_exceeds_free_configured_rate(environment):
    clock = Clock()
    limiter = service.Limiter(rate=1000, clock=lambda: clock.now, sleep=clock.sleep)
    starts = []
    async def reserve():
        await limiter.wait()
        starts.append(clock.now)
    async def batch():
        await asyncio.gather(*(reserve() for _ in range(100)))
    run(batch())
    assert starts[-1] - starts[0] >= 99 / 28 - 1e-9


def test_api_auth_admin_idempotency_conflict_legacy_resume_and_cancel(environment, monkeypatch):
    async def snapshot(self, cursor):
        return '2026-11-04T00:00:00Z', 100, 100 - cursor
    monkeypatch.setattr(service.Users, 'snapshot', snapshot)
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/v1')
    headers = {'X-Orzu-Broadcast-Key': hashlib.sha256(b'test-service-key:orzu-broadcast-v1').hexdigest()}
    data = {'id': '42_101', 'admin_id': 42, 'chat_id': 42, 'message_id': 101,
            'initial_cursor': 15, 'initial_sent': 13, 'initial_failed': 2}
    path = '/api/v1/admin/broadcasts'
    with TestClient(app) as client:
        assert client.post(path, json=data).status_code == 401
        assert client.get(path + '/42_101', headers={'X-Orzu-Broadcast-Key': 'wrong'}).status_code == 401
        non_admin = {'id': '43_101', 'admin_id': 43, 'chat_id': 43, 'message_id': 101}
        assert client.post(path, json=non_admin, headers=headers).status_code == 403
        assert client.post(path, json={**data, 'chat_id': 43}, headers=headers).status_code == 422
        assert client.post(path, json={**data, 'initial_cursor': -1}, headers=headers).status_code == 422
        created = client.post(path, json=data, headers=headers)
        assert created.status_code == 200
        assert (created.json()['cursor'], created.json()['sent'], created.json()['total']) == (15, 13, 100)
        again = client.post(path, json=data, headers=headers)
        assert again.json()['id'] == created.json()['id']
        conflict = client.post(path, json={**data, 'id': '42_102', 'message_id': 102}, headers=headers)
        assert conflict.status_code == 409
        assert conflict.json()['detail']['job']['id'] == '42_101'
        service.Store().change('42_101', 'paused', 'telegram_unavailable')
        resumed = client.post(path + '/42_101/resume', headers=headers)
        assert resumed.json()['status'] == 'queued'
        assert client.post(path + '/42_101/cancel', headers=headers).json()['status'] == 'cancelled'
        assert client.post(path + '/42_101/resume', headers=headers).json()['status'] == 'cancelled'
        assert client.get(path + '/missing', headers=headers).status_code == 404


def test_backend_copy_preserves_original_message_without_paid_broadcasts(environment, monkeypatch):
    captured = []
    async def post(self, url, json):
        captured.append((url.rsplit('/', 1)[-1], json))
        return http_response()
    def http_response():
        class Response:
            status_code = 200
            def json(self):
                return {'ok': True, 'result': {'message_id': 1}}
        return Response()
    monkeypatch.setattr('httpx.AsyncClient.post', post)
    async def copy():
        telegram = service.Telegram()
        try:
            await telegram.copy({'chat_id': 42, 'message_id': 101}, 123)
        finally:
            await telegram.close()
    run(copy())
    assert captured == [('copyMessage', {'chat_id': 123, 'from_chat_id': 42, 'message_id': 101})]


def test_worker_retries_initialization_and_never_leaves_stale_readiness(environment, monkeypatch):
    original = service.Store
    attempts = []
    def unavailable_once():
        attempts.append(True)
        if len(attempts) == 1:
            raise OSError('storage unavailable')
        return original()
    class FakeTelegram:
        async def close(self):
            pass
    class StopWorker:
        def __init__(self, *args):
            pass
        async def tick(self):
            assert service.available()
            raise asyncio.CancelledError()
    async def no_wait(seconds):
        pass
    monkeypatch.setattr(service, 'Store', unavailable_once)
    monkeypatch.setattr(service, 'Users', lambda: object())
    monkeypatch.setattr(service, 'Telegram', FakeTelegram)
    monkeypatch.setattr(service, 'Worker', StopWorker)
    monkeypatch.setattr(service.asyncio, 'sleep', no_wait)
    with pytest.raises(asyncio.CancelledError):
        run(service.broadcast_worker_loop())
    assert len(attempts) == 2
    assert not service.available()


def test_non_ascii_key_is_rejected_and_telegram_request_logs_hide_token(environment, caplog):
    assert not service.authorized('🔑' * 64)
    assert not service.authorized('')
    async def client():
        telegram = service.Telegram()
        try:
            logging.getLogger('httpx').info('HTTP Request: %s', telegram.url + '/copyMessage')
        finally:
            await telegram.close()
    with caplog.at_level(logging.INFO, logger='httpx'):
        run(client())
    assert settings.TELEGRAM_BOT_TOKEN not in caplog.text
    assert '[redacted]' in caplog.text
