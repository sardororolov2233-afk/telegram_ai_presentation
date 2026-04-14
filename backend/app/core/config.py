import os
from typing import Optional


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        for candidate in [".env", "../.env"]:
            if os.path.exists(candidate):
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        _parse_env_manually()


def _parse_env_manually() -> None:
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


_load_env()


class Settings:
    APP_NAME: str = _get_str("APP_NAME", "Telegram Mini App")
    DEBUG: bool = _get_bool("DEBUG", False)
    FRONTEND_URL: str = _get_str("FRONTEND_URL", "https://orzu-two.vercel.app")

    TELEGRAM_BOT_TOKEN: str = _get_str("TELEGRAM_BOT_TOKEN")
    TELEGRAM_WEBHOOK_URL: Optional[str] = _get("TELEGRAM_WEBHOOK_URL")

    SECRET_KEY: str = _get_str("SECRET_KEY", "change-this-secret-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 10080)

    GROQ_API_KEY: Optional[str] = _get("GROQ_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = _get("OPENROUTER_API_KEY")
    UNSPLASH_ACCESS_KEY: Optional[str] = _get("UNSPLASH_ACCESS_KEY")

    SUPABASE_URL: str = _get_str("SUPABASE_URL")
    SUPABASE_KEY: str = _get_str("SUPABASE_KEY")


settings = Settings()
