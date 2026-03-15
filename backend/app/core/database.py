import asyncio
from typing import Generator
from supabase import create_client, Client
from app.core.config import settings

# Global client instance
_supabase: Client | None = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY not set in environment or config")
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase

async def get_db() -> Client:
    """Dependency injector for FastAPI endpoints"""
    # Supabase HTTPX asosida ishlaydi, shunga sinxron obyekt qaytarish xavfsiz.
    # Lekin barcha so'rovlar await asyncio.to_thread bilan berilishi ma'qul.
    yield get_supabase()
