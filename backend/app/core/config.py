"""
Settings module — pydantic BaseSettings o'rniga python-dotenv ishlatiladi.
Python 3.14 + pydantic 1.x da BaseSettings xato beradi.
"""
import os
from pathlib import Path
from typing import Optional


def _load_env() -> None:
    """Root yoki backend papkasidagi .env faylni yuklaydi."""
    # python-dotenv mavjud bo'lsa ishlatadi
    try:
        from dotenv import load_dotenv
        for candidate in [".env", "../.env"]:
            if os.path.exists(candidate):
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        # python-dotenv o'rnatilmagan — os.environ dan o'qiladi
        _parse_env_manually()


def _parse_env_manually() -> None:
    """python-dotenv o'rnatilmagan holda .env ni qo'lda parse qiladi."""
    for candidate in [".env", "../.env"]:
        if not os.path.exists(candidate):
            continue
        with open(candidate, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


def _get(key: str, default: str = "") -> Optional[str]:
    """Ortiqcha bo'sh joylarni olib, bo'sh string ni None ga aylantiradi."""
    val = os.environ.get(key, default).strip()
    return None if val == "" else val


def _get_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip() or default


def _get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)).strip())
    except (ValueError, AttributeError):
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("true", "1", "yes")


# .env ni yuklash
_load_env()


class Settings:
    """Barcha sozlamalar — environment variable orqali."""

    APP_NAME: str = _get_str("APP_NAME", "Telegram Mini App")
    DEBUG: bool = _get_bool("DEBUG", False)
    FRONTEND_URL: str = _get_str("FRONTEND_URL", "https://your-domain.com")

    # Database (Railway postgres:// ni avtomatik asyncpg formatga o'giradi)
    _raw_db_url: str = _get_str("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
    DATABASE_URL: str = (
        _raw_db_url
        .replace("postgres://", "postgresql+asyncpg://", 1)
        .replace("postgresql://", "postgresql+asyncpg://", 1)
        if _raw_db_url.startswith(("postgres://", "postgresql://"))
        else _raw_db_url
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = _get_str("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: Optional[str] = _get("TELEGRAM_WEBHOOK_URL")

    # Payment
    PAYMENT_PROVIDER_TOKEN: Optional[str] = _get("PAYMENT_PROVIDER_TOKEN")
    PAYME_MERCHANT_ID: Optional[str] = _get("PAYME_MERCHANT_ID")
    PAYME_SECRET_KEY: Optional[str] = _get("PAYME_SECRET_KEY")
    CLICK_SERVICE_ID: Optional[str] = _get("CLICK_SERVICE_ID")
    CLICK_SECRET_KEY: Optional[str] = _get("CLICK_SECRET_KEY")

    # JWT
    SECRET_KEY: str = _get_str("SECRET_KEY", "change-this-secret-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)

    # Redis
    REDIS_URL: str = _get_str("REDIS_URL", "redis://localhost:6379")

    # OpenAI
    GROQ_API_KEY: Optional[str] = _get("GROQ_API_KEY")
    UNSPLASH_ACCESS_KEY: Optional[str] = _get("UNSPLASH_ACCESS_KEY")

    # Supabase
    SUPABASE_URL: Optional[str] = _get("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = _get("SUPABASE_KEY")

settings = Settings()
