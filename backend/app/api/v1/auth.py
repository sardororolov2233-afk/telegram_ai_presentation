import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client
from app.core.database import get_db
from app.utils.telegram_auth import validate_telegram_init_data, create_access_token
from app.services.commerce import register, parse_referrer

router = APIRouter(prefix='/auth', tags=['Auth'])


class TelegramAuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: dict


@router.post('/telegram', response_model=AuthResponse)
async def telegram_auth(body: TelegramAuthRequest, db: Client = Depends(get_db)):
    user_data = validate_telegram_init_data(body.init_data)
    if not user_data:
        raise HTTPException(401, 'Noto‘g‘ri yoki eskirgan Telegram ma’lumotlari')
    await register(db, user_data, parse_referrer(user_data.get('_start_param')))
    response = await asyncio.to_thread(db.table('users').select('*').eq('telegram_id', user_data['id']).execute)
    user = response.data[0]
    if not user.get('is_active', True):
        raise HTTPException(403, 'Hisob faol emas')
    return AuthResponse(access_token=create_access_token(user_data['id']), user={
        'id': user['telegram_id'], 'first_name': user.get('first_name', ''), 'username': user.get('username'),
        'balance': float(user.get('balance') or 0), 'role': user.get('role', 'user')})
