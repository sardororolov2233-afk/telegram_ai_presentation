from fastapi import APIRouter, Depends
from supabase import Client
from app.core.database import get_db
from app.core.config import settings
from app.routes.deps import get_current_user
from app.services.commerce import rpc, status, POLICY_TEXT, quote

router = APIRouter(prefix='/commerce', tags=['Account'])


@router.get('')
async def account(user: dict = Depends(get_current_user), db: Client = Depends(get_db)):
    result = await status(db, user['telegram_id'])
    result['bot_username'] = settings.TELEGRAM_BOT_USERNAME
    result['referral_link'] = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start=ref_{user['telegram_id']}"
    result['policy'] = POLICY_TEXT
    result['quotes'] = {service: quote(result, service) for service in ('presentation', 'course', 'referat', 'article')}
    return result


@router.post('/subscribe')
async def subscribe(user: dict = Depends(get_current_user), db: Client = Depends(get_db)):
    return await rpc(db, 'commerce_subscribe', p_user_id=user['telegram_id'])
