import hashlib
import hmac
import json
import time
from urllib.parse import unquote, parse_qsl
from typing import Optional

from app.core.config import settings


def validate_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Telegram WebApp initData ni tekshiradi.
    Haqiqiy bo'lsa user ma'lumotlarini qaytaradi, aks holda None.
    """
    try:
        parsed = dict(parse_qsl(unquote(init_data), strict_parsing=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # Auth sanasini tekshirish (1 soat)
    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > 3600:
        return None

    # Data-check-string yasash
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Kalitni hisoblash
    secret_key = hmac.new(
        b"WebAppData",
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()

    # Hash tekshirish
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # User ma'lumotlarini qaytarish
    user_data = parsed.get("user")
    if user_data:
        try:
            return json.loads(user_data)
        except json.JSONDecodeError:
            return None

    return parsed


def create_access_token(telegram_id: int) -> str:
    """JWT token yaratadi."""
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": str(telegram_id),
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[int]:
    """JWT tokenni decode qiladi."""
    import jwt

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return int(payload["sub"])
    except Exception:
        return None
