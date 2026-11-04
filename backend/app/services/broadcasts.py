"""Durable, single-host broadcasts; no Telegram calls run in request handlers."""
import asyncio
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import logging
import re
from pathlib import Path
import sqlite3
import time

import httpx

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)
ACTIVE = ('queued', 'running', 'paused')
PAGE_SIZE = 500
CONCURRENCY = 5
_worker_available = False


def admin_ids():
    return {int(value.strip()) for value in settings.ADMIN_ID.split(',')
            if value.strip().isdigit() and 0 < int(value.strip()) < 2**53}


def configured():
    return bool(admin_ids() and settings.SUPABASE_KEY and settings.TELEGRAM_BOT_TOKEN)


def storage_directory():
    return Path(settings.BROADCAST_STORAGE_DIR) if settings.BROADCAST_STORAGE_DIR else Path(settings.JOB_STORAGE_DIR) / 'broadcasts'


def available():
    return configured() and _worker_available


def authorized(key):
    expected = hashlib.sha256((settings.SUPABASE_KEY + ':orzu-broadcast-v1').encode()).hexdigest()
    return configured() and bool(key) and bool(re.fullmatch('[0-9a-f]{64}', key)) and hmac.compare_digest(key, expected)


class ActiveBroadcast(Exception):
    def __init__(self, job):
        self.job = job


class Store:
    def __init__(self, directory=None):
        directory = Path(directory) if directory is not None else storage_directory()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / 'broadcasts.sqlite3'
        with self.connection() as db:
            db.executescript('''
                create table if not exists broadcasts (
                    id text primary key, admin_id integer not null, chat_id integer not null,
                    message_id integer not null, status text not null, cursor integer not null,
                    upper_id integer not null, snapshot_at text not null, total integer not null,
                    sent integer not null default 0, failed integer not null default 0,
                    resume_at real not null default 0, last_error text,
                    notified integer not null default 0, created_at real not null
                );
                create table if not exists recipients (
                    job_id text not null, user_id integer not null, status text not null,
                    primary key(job_id,user_id)
                );
            ''')
        self.path.chmod(0o600)

    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('pragma journal_mode=WAL')
        return contextlib.closing(db)

    def get(self, job_id):
        with self.connection() as db:
            row = db.execute('select * from broadcasts where id=?', (job_id,)).fetchone()
            return dict(row) if row else None

    def active(self):
        with self.connection() as db:
            row = db.execute("select * from broadcasts where status in ('queued','running','paused') order by created_at limit 1").fetchone()
            return dict(row) if row else None

    def create(self, data, snapshot, upper, remaining):
        with self.connection() as db:
            db.execute('begin immediate')
            existing = db.execute('select * from broadcasts where id=?', (data['id'],)).fetchone()
            if existing:
                return dict(existing)
            active = db.execute("select * from broadcasts where status in ('queued','running','paused') limit 1").fetchone()
            if active:
                raise ActiveBroadcast(dict(active))
            sent, failed = data.get('initial_sent', 0), data.get('initial_failed', 0)
            db.execute('''insert into broadcasts
                (id,admin_id,chat_id,message_id,status,cursor,upper_id,snapshot_at,total,sent,failed,created_at)
                values (?,?,?,?,'queued',?,?,?,?,?,?,?)''',
                (data['id'], data['admin_id'], data['chat_id'], data['message_id'],
                 data.get('initial_cursor', 0), upper, snapshot, remaining + sent + failed,
                 sent, failed, time.time()))
            db.commit()
        return self.get(data['id'])

    def change(self, job_id, status, error=None):
        with self.connection() as db:
            db.execute("update broadcasts set status=?,last_error=? where id=? and status in ('queued','running','paused')",
                       (status, error, job_id))
            db.commit()
        return self.get(job_id)

    def resume(self, job_id):
        with self.connection() as db:
            db.execute("update broadcasts set status='queued',notified=0,last_error=null where id=? and status='paused'", (job_id,))
            db.commit()
        return self.get(job_id)

    def cooldown(self, job_id, until):
        with self.connection() as db:
            db.execute('update broadcasts set resume_at=max(resume_at,?) where id=?', (until, job_id))
            db.commit()

    def runnable(self):
        with self.connection() as db:
            row = db.execute("select * from broadcasts where status in ('queued','running') order by created_at limit 1").fetchone()
            return dict(row) if row else None

    def page(self, job_id, users):
        with self.connection() as db:
            db.executemany("insert or ignore into recipients(job_id,user_id,status) values (?,?,'pending')",
                           ((job_id, user) for user in users))
            db.commit()
            return [row['user_id'] for row in db.execute(
                "select user_id from recipients where job_id=? and status='pending' order by user_id", (job_id,))]

    def result(self, job_id, user_id, status):
        with self.connection() as db:
            db.execute('begin immediate')
            changed = db.execute("update recipients set status=? where job_id=? and user_id=? and status='pending'",
                                 (status, job_id, user_id)).rowcount
            if changed:
                column = 'sent' if status == 'sent' else 'failed'
                db.execute(f'update broadcasts set {column}={column}+1 where id=?', (job_id,))
            db.commit()

    def advance(self, job_id, cursor):
        with self.connection() as db:
            db.execute('update broadcasts set cursor=?,resume_at=0 where id=?', (cursor, job_id))
            db.commit()

    def notification(self):
        with self.connection() as db:
            db.execute('begin immediate')
            row = db.execute("select * from broadcasts where status in ('completed','cancelled','paused') and notified=0 order by created_at limit 1").fetchone()
            if row:
                db.execute('update broadcasts set notified=1 where id=?', (row['id'],))
            db.commit()
            return dict(row) if row else None


class Users:
    def __init__(self, db=None):
        self.db = db or get_db()

    async def snapshot(self, cursor):
        at = datetime.now(timezone.utc).isoformat()
        def query():
            rows = self.db.table('users').select('telegram_id').gt('telegram_id', cursor).lte('created_at', at).order('telegram_id', desc=True).limit(1).execute()
            upper = int(rows.data[0]['telegram_id']) if rows.data else cursor
            counted = self.db.table('users').select('telegram_id', count='exact').gt('telegram_id', cursor).lte('telegram_id', upper).lte('created_at', at).limit(1).execute()
            return at, upper, counted.count or 0
        return await asyncio.to_thread(query)

    async def page(self, job):
        def query():
            rows = self.db.table('users').select('telegram_id').gt('telegram_id', job['cursor']).lte('telegram_id', job['upper_id']).lte('created_at', job['snapshot_at']).order('telegram_id').limit(PAGE_SIZE).execute()
            return [int(row['telegram_id']) for row in rows.data]
        return await asyncio.to_thread(query)


class TelegramFailure(Exception):
    def __init__(self, code, description='', parameters=None):
        self.code, self.description, self.parameters = code, description, parameters or {}


class Telegram:
    def __init__(self):
        # httpx INFO request logs otherwise include the Bot API token in the URL.
        log = logging.getLogger('httpx')
        if not any(isinstance(item, _TokenFilter) for item in log.filters):
            log.addFilter(_TokenFilter())
        self.client = httpx.AsyncClient(timeout=25)
        self.url = 'https://api.telegram.org/bot' + settings.TELEGRAM_BOT_TOKEN

    async def call(self, method, body):
        # Do not log exception strings/request URLs: Telegram embeds a token in them.
        try:
            response = await self.client.post(self.url + '/' + method, json=body)
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramFailure(503) from None
        if not payload.get('ok'):
            raise TelegramFailure(payload.get('error_code', response.status_code),
                                  payload.get('description', ''), payload.get('parameters'))
        return payload['result']

    async def copy(self, job, recipient):
        return await self.call('copyMessage', {'chat_id': recipient, 'from_chat_id': job['chat_id'],
                                               'message_id': job['message_id']})

    async def report(self, job):
        labels = {'completed': 'Yakunlandi', 'cancelled': 'Bekor qilindi', 'paused': 'Vaqtincha to‘xtatildi'}
        await self.call('sendMessage', {'chat_id': job['admin_id'], 'text':
            f"📢 {labels[job['status']]}\nYuborildi: {job['sent']}. Yuborilmadi: {job['failed']}. Jami: {job['total']}.\n/admin — holat va davom ettirish."})

    async def close(self):
        await self.client.aclose()


class _TokenFilter(logging.Filter):
    def filter(self, record):
        token = settings.TELEGRAM_BOT_TOKEN
        if token:
            record.msg = record.getMessage().replace(token, '[redacted]')
            record.args = ()
        return True


class Limiter:
    def __init__(self, rate=None, clock=time.time, sleep=asyncio.sleep):
        self.interval = 1 / max(1, min(rate or settings.BROADCAST_RATE_PER_SECOND, 28))
        self.clock, self.sleep = clock, sleep
        self.next_at, self.pause_until = 0, 0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            while True:
                delay = max(self.next_at, self.pause_until) - self.clock()
                if delay <= 0:
                    self.next_at = self.clock() + self.interval
                    return
                await self.sleep(delay)


class Worker:
    def __init__(self, store, users, telegram, limiter=None):
        self.store, self.users, self.telegram = store, users, telegram
        self.limiter = limiter or Limiter()

    def active(self, job_id):
        return self.store.get(job_id)['status'] in ('queued', 'running')

    async def deliver(self, job, recipient):
        attempt = 0
        while attempt < 4:
            if not self.active(job['id']):
                return
            await self.limiter.wait()
            if not self.active(job['id']):
                return
            try:
                await self.telegram.copy(job, recipient)
                self.store.result(job['id'], recipient, 'sent')
                return
            except TelegramFailure as exc:
                if exc.code == 429:
                    until = self.limiter.clock() + max(1, float(exc.parameters.get('retry_after', 1)))
                    self.limiter.pause_until = max(self.limiter.pause_until, until)
                    self.store.cooldown(job['id'], until)
                    # Flood waits do not exhaust transport retries or lose this recipient.
                    continue
                source_error = any(value in exc.description.lower() for value in (
                    'message to copy not found', 'message can\'t be copied', 'message cannot be copied',
                    'message_id_invalid', 'from_chat_id', 'source message'))
                if source_error:
                    self.store.change(job['id'], 'paused', 'source_unavailable')
                    return
                recipient_error = any(value in exc.description.lower() for value in (
                    'chat not found', 'user is deactivated', 'user not found', 'chat_write_forbidden'))
                if exc.code == 403 or (exc.code == 400 and recipient_error):
                    self.store.result(job['id'], recipient, 'failed')
                    return
                if exc.code == 400:
                    self.store.change(job['id'], 'paused', 'telegram_message_rejected')
                    return
                if exc.code == 401:
                    self.store.change(job['id'], 'paused', 'telegram_authentication_failed')
                    return
                if attempt == 3:
                    self.store.change(job['id'], 'paused', 'telegram_unavailable')
                    return
                await self.limiter.sleep(2 ** attempt)
                attempt += 1
            except Exception:
                self.store.change(job['id'], 'paused', 'telegram_unavailable')
                return

    async def run_job(self, job):
        self.store.change(job['id'], 'running')
        self.limiter.pause_until = max(self.limiter.pause_until, job['resume_at'])
        while self.active(job['id']):
            current = self.store.get(job['id'])
            try:
                users = await self.users.page(current)
            except Exception:
                self.store.change(job['id'], 'paused', 'database_unavailable')
                return
            if not users:
                self.store.change(job['id'], 'completed')
                return
            pending = self.store.page(job['id'], users)
            for start in range(0, len(pending), CONCURRENCY):
                await asyncio.gather(*(self.deliver(job, recipient) for recipient in pending[start:start + CONCURRENCY]))
                if not self.active(job['id']):
                    return
            self.store.advance(job['id'], users[-1])

    async def tick(self):
        job = self.store.runnable()
        if job:
            await self.run_job(job)
        report = self.store.notification()
        if report:
            try:
                await self.limiter.wait()
                await self.telegram.report(report)
            except Exception:
                # Report is best-effort and is never allowed to repeat the campaign.
                logger.warning('Broadcast admin report unavailable')
        return bool(job or report)


@contextlib.contextmanager
def worker_lock(directory):
    path = Path(directory) / 'broadcast-worker.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


async def broadcast_worker_loop():
    global _worker_available
    if not configured():
        _worker_available = False
        return
    telegram = Telegram()
    try:
        while True:
            try:
                # Probe storage even in non-owning Uvicorn processes so their health
                # accurately advertises the same worker capability.
                store = Store()
                source = Users()
                _worker_available = True
                with worker_lock(storage_directory()) as acquired:
                    if acquired:
                        worker = Worker(store, source, telegram)
                        while True:
                            active = await worker.tick()
                            if not active:
                                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                _worker_available = False
                logger.warning('Broadcast worker retrying after storage error')
            await asyncio.sleep(2)
    finally:
        _worker_available = False
        await telegram.close()
