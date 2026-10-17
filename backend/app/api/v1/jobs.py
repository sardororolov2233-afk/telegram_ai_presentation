import asyncio
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from supabase import Client
from app.core.config import settings
from app.core.database import get_db
from app.routes.deps import get_current_user

router = APIRouter(prefix='/jobs', tags=['Orders'])


async def owned_job(db, user_id, request_id):
    response = await asyncio.to_thread(db.table('commerce_jobs').select('*').eq('id', str(request_id)).eq('user_id', user_id).execute)
    if not response.data:
        raise HTTPException(404, 'Buyurtma topilmadi')
    return response.data[0]


@router.get('/{request_id}')
async def job_status(request_id: UUID, db: Client = Depends(get_db), user: dict = Depends(get_current_user)):
    job = await owned_job(db, user['telegram_id'], request_id)
    result = job.get('result') or {}
    return {'id': job['id'], 'status': job['status'], 'service': job['service'],
        'telegram_sent': result.get('telegram_sent', False), 'slide_count': result.get('slide_count'),
        'message': 'Ish yakunlanmadi. Band qilingan pul yoki limit qaytarildi.' if job['status'] == 'failed' else None,
        'download_url': f"/api/v1/jobs/{job['id']}/download" if job['status'] == 'completed' else None}


@router.get('/{request_id}/download')
async def job_download(request_id: UUID, db: Client = Depends(get_db), user: dict = Depends(get_current_user)):
    job = await owned_job(db, user['telegram_id'], request_id)
    if job['status'] != 'completed':
        raise HTTPException(409, 'Fayl hali tayyor emas')
    path = Path((job.get('result') or {}).get('document_path', '')).resolve()
    root = (Path(settings.JOB_STORAGE_DIR) / 'outputs').resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, 'Fayl mavjud emas')
    return FileResponse(path, filename=f"{job['service']}_{job['id']}{path.suffix}")
