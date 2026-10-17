"""A Postgres-backed queue survives API restarts. Run on an always-on server/container."""
import asyncio
import contextlib
import logging
from pathlib import Path
from uuid import uuid4
from app.core.database import get_db
from app.services.commerce import rpc, CommerceError
from app.services.presentation.pipeline import PresentationPipeline
from app.services.article.pipeline import ArticlePipeline
from app.services.presentation.telegram_sender import send_status_message

logger = logging.getLogger(__name__)


class LeaseLost(RuntimeError):
    pass


async def heartbeat(db, job_id, worker_id):
    while True:
        await asyncio.sleep(30)
        if not await rpc(db, 'commerce_job_heartbeat', p_request_id=job_id, p_worker_id=worker_id):
            raise LeaseLost('Job is no longer owned by this worker')


async def process_job(db, job, worker_id):
    payload = dict(job['payload'])
    send_to_telegram = payload.pop('send_to_telegram', True)
    payload.pop('image_hashes', None)
    telegram_id = job['user_id'] if send_to_telegram else None
    images = payload.get('user_images') or []
    operation = None
    pulse = asyncio.create_task(heartbeat(db, job['id'], worker_id))
    done = False
    try:
        if job.get('attempts', 1) > 3:
            raise RuntimeError('Worker restart limit reached')
        if telegram_id:
            await send_status_message(telegram_id, '⏳ Buyurtmangiz tayyorlanmoqda. Natijani mini ilovada ham olishingiz mumkin.')
        pipeline = PresentationPipeline() if job['service'] == 'presentation' else ArticlePipeline()
        operation = asyncio.create_task(pipeline.run(**payload, telegram_id=telegram_id))
        completed, _ = await asyncio.wait([operation, pulse], return_when=asyncio.FIRST_COMPLETED)
        if pulse in completed:
            await pulse  # A lost lease must stop the old worker before it delivers a second file.
        result = await operation
        done = await rpc(db, 'commerce_finish_job', p_request_id=job['id'], p_worker_id=worker_id,
            p_success=True, p_result=result, p_error=None)
    except (asyncio.CancelledError, LeaseLost, CommerceError):
        # Leave the persisted job for the next worker; never discard it on process shutdown.
        raise
    except Exception as exc:
        logger.exception('Job %s failed', job['id'])
        done = await rpc(db, 'commerce_finish_job', p_request_id=job['id'], p_worker_id=worker_id,
            p_success=False, p_result=None, p_error=str(exc))
        if telegram_id and done:
            await send_status_message(telegram_id, 'Ishni tayyorlash yakunlanmadi. Band qilingan pul yoki limit qaytarildi.')
    finally:
        pulse.cancel()
        if operation and not operation.done():
            operation.cancel()
        with contextlib.suppress(asyncio.CancelledError, CommerceError, LeaseLost):
            await pulse
        if operation:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await operation
        if done:
            for path in images:
                Path(path).unlink(missing_ok=True)


async def worker_loop():
    worker_id = str(uuid4())
    db = get_db()
    while True:
        try:
            await rpc(db, 'commerce_recover_expired')
            job = await rpc(db, 'commerce_claim_job', p_worker_id=worker_id)
            if job:
                await process_job(db, job, worker_id)
            else:
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Generation worker error')
            await asyncio.sleep(5)
