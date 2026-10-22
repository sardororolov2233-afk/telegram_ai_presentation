from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import contextlib
from pathlib import Path
from fastapi.responses import JSONResponse, FileResponse

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import get_db
from app.services.commerce import CommerceError, rpc
from app.services.job_worker import worker_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.DEBUG and (len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY.startswith(('change-', 'REPLACE_', 'YOUR_'))):
        raise RuntimeError('SECRET_KEY kamida 32 belgili tasodifiy qiymat bo‘lsin')
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_BOT_USERNAME or not settings.OPENROUTER_API_KEY:
        raise RuntimeError('TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME va OPENROUTER_API_KEY kerak')
    policy = await rpc(get_db(), 'commerce_policy')
    if policy.get('access_mode') != 'referral_only':
        raise RuntimeError('20261022_referral_only.sql migratsiyasini qo‘llang')
    await rpc(get_db(), 'commerce_recover_expired')
    workers = [asyncio.create_task(worker_loop()) for _ in range(max(1, min(settings.JOB_WORKERS, 4)))]
    try:
        yield
    finally:
        for task in workers:
            task.cancel()
        for task in workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(CommerceError)
async def commerce_error(request, exc):
    code = (503 if exc.code == 'unavailable' else 410 if exc.code in {'subscriptions_disabled', 'payments_disabled'}
        else 409 if exc.code == 'request_conflict' else 402)
    return JSONResponse(status_code=code, content={'detail': str(exc), 'code': exc.code})

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.abspath(os.path.join(current_dir, "../static"))
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get('/miniapp', include_in_schema=False)
async def mini_app():
    return FileResponse(Path(static_dir) / 'miniapp.html')

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
