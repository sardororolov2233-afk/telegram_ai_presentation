from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.services.broadcasts import Store, Users, ActiveBroadcast, admin_ids, authorized

router = APIRouter(prefix='/admin/broadcasts', tags=['Admin broadcasts'])


def require_worker_key(x_orzu_broadcast_key: str | None = Header(default=None)):
    if not authorized(x_orzu_broadcast_key):
        raise HTTPException(401, 'Unauthorized')


class BroadcastRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(max_length=100)
    admin_id: int = Field(gt=0, lt=2**53)
    chat_id: int = Field(gt=0, lt=2**53)
    message_id: int = Field(gt=0, lt=2**31)
    initial_cursor: int = Field(default=0, ge=0, lt=2**53)
    initial_sent: int = Field(default=0, ge=0, le=10**9)
    initial_failed: int = Field(default=0, ge=0, le=10**9)

    @model_validator(mode='after')
    def validate_source(self):
        if self.chat_id != self.admin_id or self.id != f'{self.admin_id}_{self.message_id}':
            raise ValueError('Invalid broadcast source')
        return self


def find(job_id):
    try:
        job = Store().get(job_id)
    except Exception:
        raise HTTPException(503, 'Broadcast storage unavailable') from None
    if not job:
        raise HTTPException(404, 'Broadcast not found')
    return job


@router.post('', dependencies=[Depends(require_worker_key)])
async def create(data: BroadcastRequest):
    if data.admin_id not in admin_ids():
        raise HTTPException(403, 'Admin required')
    try:
        store = Store()
        existing = store.get(data.id)
        if existing:
            return existing
        snapshot, upper, remaining = await Users().snapshot(data.initial_cursor)
        return store.create(data.model_dump(), snapshot, upper, remaining)
    except ActiveBroadcast as exc:
        raise HTTPException(409, detail={'code': 'broadcast_active', 'job': exc.job})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Broadcast storage unavailable') from None


@router.get('/{job_id}', dependencies=[Depends(require_worker_key)])
async def status(job_id: str):
    return find(job_id)


@router.post('/{job_id}/cancel', dependencies=[Depends(require_worker_key)])
async def cancel(job_id: str):
    find(job_id)
    return Store().change(job_id, 'cancelled')


@router.post('/{job_id}/resume', dependencies=[Depends(require_worker_key)])
async def resume(job_id: str):
    job = find(job_id)
    if job['status'] == 'paused':
        return Store().resume(job_id)
    return job
