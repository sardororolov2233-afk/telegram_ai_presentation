from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Telegram Mini App"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/telegram_app"

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: Optional[str] = None

    # Payment (Telegram Stars yoki Payme/Click)
    PAYMENT_PROVIDER_TOKEN: Optional[str] = None
    PAYME_MERCHANT_ID: Optional[str] = None
    PAYME_SECRET_KEY: Optional[str] = None
    CLICK_SERVICE_ID: Optional[str] = None
    CLICK_SECRET_KEY: Optional[str] = None

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 kun

    # Redis (cache uchun)
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
