from supabase import create_client, Client
from app.core.config import settings

_supabase: Client | None = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL va SUPABASE_KEY .env faylida o'rnatilmagan!")
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase

def get_db() -> Client:
    return get_supabase()
