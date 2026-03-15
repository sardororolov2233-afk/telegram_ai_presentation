import os, shutil

# 1. Delete pycache
pycache_dir = r"d:\Новая папка\backend\app\__pycache__"
if os.path.exists(pycache_dir):
    shutil.rmtree(pycache_dir, ignore_errors=True)

# 2. Rewrite main.py
main_path = r"d:\Новая папка\backend\app\main.py"
content = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
"""
with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)

# 3. Read it back
with open(main_path, "r", encoding="utf-8") as f:
    print("Does it contain engine?", "engine" in f.read())
