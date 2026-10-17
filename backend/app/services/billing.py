"""Atomic accounting for the retained design and obyektivka endpoints."""
import asyncio
import contextlib
from functools import wraps
from uuid import uuid4
from app.services.commerce import rpc, status


async def keep_reservation(db, user_id, request_id):
    while True:
        await asyncio.sleep(30)
        await rpc(db, 'commerce_heartbeat', p_user_id=user_id, p_request_id=request_id)


def billed_route(service):
    def decorate(handler):
        @wraps(handler)
        async def wrapped(*args, **kwargs):
            db, user_id = kwargs['db'], kwargs['user']['telegram_id']
            request_id = str(uuid4())
            await rpc(db, 'commerce_reserve', p_user_id=user_id, p_service=service, p_request_id=request_id)
            pulse = asyncio.create_task(keep_reservation(db, user_id, request_id))
            try:
                result = await handler(*args, **kwargs)
            except BaseException:
                await asyncio.shield(rpc(db, 'commerce_finish', p_user_id=user_id, p_request_id=request_id, p_success=False))
                raise
            else:
                await rpc(db, 'commerce_finish', p_user_id=user_id, p_request_id=request_id, p_success=True)
                if hasattr(result, 'balance'):
                    result.balance = (await status(db, user_id))['balance']
                return result
            finally:
                pulse.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pulse
        return wrapped
    return decorate
