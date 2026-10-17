import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from typing import Optional

from app.core.config import settings


def validate_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Telegram WebApp initData ni tekshiradi.
    Haqiqiy bo'lsa user ma'lumotlarini qaytaradi, aks holda None.
    """
    try:
        # Decode once: double decoding breaks names containing literal '+', '%' or '&'.
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # Auth sanasini tekshirish (1 soat)
    try:
        auth_date = int(parsed.get("auth_date", 0))
    except (TypeError, ValueError):
        return None
    if not 0 <= time.time() - auth_date <= 3600:
        return None

    # Data-check-string yasash
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Kalitni hisoblash — positional argumentlar (to'g'ri sintaksis)
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
            user = json.loads(user_data)
            if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user.get("is_bot"):
                return None
            user["_start_param"] = parsed.get("start_param")
            return user
        except json.JSONDecodeError:
            return None

    return None


def create_access_token(telegram_id: int) -> str:
    """JWT token yaratadi."""
    import jwt
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(telegram_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
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
