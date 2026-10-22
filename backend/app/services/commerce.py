"""Shared referral-only RPC contract; all credit changes run inside Postgres."""
import asyncio
import logging

logger = logging.getLogger(__name__)
QUOTA_COSTS = {"presentation": 1, "course": 2, "design": 1, "referat": 1, "article": 1, "obyektivka": 1}
ERROR_MESSAGES = {
    "insufficient_referral_credits": "Taklif kvotasi yetarli emas. Har bir yangi do‘st — 1 kvota. Taqdimot va dizayn uchun 1, kurs ishi uchun 2 kvota kerak.",
    "subscriptions_disabled": "Obuna bekor qilingan. Kvota faqat yangi do‘st taklif qilish orqali olinadi.",
    "payments_disabled": "To‘lovlar yopilgan. Do‘st taklif qilib kvota oling.",
    "invalid_service": "Noto‘g‘ri xizmat tanlandi.",
    "user_not_registered": "Avval botda /start buyrug‘ini bosing.",
    "request_conflict": "Buyurtma identifikatori boshqa so‘rovga tegishli.",
    "unavailable": "Hisob tizimiga ulanib bo‘lmadi. Birozdan so‘ng qayta urinib ko‘ring.",
}


class CommerceError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(ERROR_MESSAGES.get(code, ERROR_MESSAGES["unavailable"]))


async def rpc(client, function: str, **params):
    try:
        response = await asyncio.to_thread(client.rpc(function, params).execute)
        return response.data
    except Exception as exc:
        code = next((code for code in ERROR_MESSAGES if code in str(exc)), "unavailable")
        logger.error("Commerce RPC %s failed: %s", function, exc)
        raise CommerceError(code) from exc


async def register(client, telegram_user, referrer_id=None):
    return await rpc(client, "commerce_register", p_user_id=telegram_user["id"],
        p_first_name=telegram_user.get("first_name", ""), p_last_name=telegram_user.get("last_name"),
        p_username=telegram_user.get("username"), p_referrer_id=referrer_id)


async def status(client, user_id):
    return await rpc(client, "commerce_status", p_user_id=user_id)


def parse_referrer(value):
    if not value or not value.startswith("ref_"):
        return None
    suffix = value[4:]
    if suffix.isascii() and suffix.isdigit() and 0 < int(suffix) < 2**63:
        return int(suffix)
    return None


def quote(account, service):
    """UI preview only. The reserve RPC rechecks this under a row lock."""
    required = QUOTA_COSTS[service]
    if service in {"referat", "article", "obyektivka"} and int(account.get("standard_free_remaining") or 0) > 0:
        required = 0
    available = int(account.get("referral_credits") or 0)
    return {"allowed": available >= required, "amount": 0,
        "source": "referral" if required else "free", "required_credits": required,
        "available_credits": available, "missing_credits": max(0, required - available),
        "reason": "insufficient_referral_credits" if available < required else None}


POLICY_TEXT = (
    "🎁 Har bir yangi, kanal a’zoligi tasdiqlangan do‘st — 1 ta muddatsiz kvota.\n"
    "📊 Taqdimot — 1 kvota. 🎨 Dizayn — 1 kvota. 📚 Kurs ishi — 2 kvota.\n"
    "Kvotalar umumiy: bir xizmatga sarflangan kvota boshqa xizmatga qayta sarflanmaydi.\n\n"
    "📄 Referat/mustaqil ish, maqola va obyektivka uchun jami dastlabki 3 ta foydalanish bepul. Keyingi har biri — 1 kvota.\n"
    "Obuna va pulli xaridlar bekor qilingan. Kvota faqat do‘st taklif qilish orqali olinadi.\n"
    "Bitta taqdimot uchun ko‘pi bilan 3 ta AI rasm yaratiladi; qo‘shimcha rasm joylarida ular qayta ishlatiladi."
)
