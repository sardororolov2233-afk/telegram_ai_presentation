from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from supabase import Client
from app.core.database import get_db
from app.routes.deps import get_current_user
from app.services.commerce import rpc

router = APIRouter(prefix='/articles', tags=['Articles'])


@router.post('/generate', status_code=202)
async def generate_article(request: Request, topic: str = Form(..., min_length=3, max_length=500),
    author: str = Form(..., min_length=2, max_length=150), language: Literal['uz', 'ru', 'en'] = Form('uz'),
    references: str = Form('', max_length=10000), send_to_telegram: bool = Form(True),
    idempotency_key: UUID = Header(...), db: Client = Depends(get_db), user: dict = Depends(get_current_user)):
    if len(topic.strip()) < 3 or len(author.strip()) < 2:
        raise HTTPException(400, 'Mavzu va muallifni to‘liq kiriting')
    if 'send_to_telegram' not in await request.form():
        send_to_telegram = True
    payload = {'topic': topic.strip(), 'author': author.strip(), 'language': language,
        'references': references, 'send_to_telegram': send_to_telegram}
    charge = await rpc(db, 'commerce_enqueue', p_user_id=user['telegram_id'], p_service='article',
        p_request_id=str(idempotency_key), p_payload=payload)
    return {'id': str(idempotency_key), 'status': 'queued' if charge['status'] == 'reserved' else charge['status'],
        'telegram_sent': False}
