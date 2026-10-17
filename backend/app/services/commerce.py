"""Shared RPC contract with Orzu/commerce.py; all mutations run inside Postgres."""
import asyncio
import logging

logger = logging.getLogger(__name__)
PAYMENT_CARD = "9860020144204623"
SUBSCRIPTION_PRICE = 25000
PRICES = {"presentation": 10000, "course": 30000, "referat": 8000, "article": 10000, "design": 5000, "obyektivka": 10000}
ERROR_MESSAGES = {
    "duplicate_receipt": "Ushbu chek avval tasdiqlangan. Uni qayta ishlatib bo‘lmaydi.",
    "insufficient_balance": "Balans yetarli emas. Do‘st taklif qiling yoki hisobni to‘ldiring.",
    "presentation_access_required": "5 ta do‘st taklif qiling yoki 25 000 so‘mga bir oylik obuna oling.",
    "subscription_active": "Bir oylik obuna allaqachon faol. Qo‘shimcha limit uchun 5 ta do‘st taklif qiling yoki har bir taqdimotga 10 000 so‘m to‘lang.",
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
    if service == "presentation":
        if account.get("subscription_active") and account.get("subscription_remaining", 0) > 0:
            return {"allowed": True, "amount": 0, "source": "subscription"}
        if account.get("referral_presentations", 0) > 0:
            return {"allowed": True, "amount": 0, "source": "referral"}
        if not account.get("presentation_period_active"):
            return {"allowed": False, "amount": None, "reason": "presentation_access_required"}
    if service == "course" and account.get("course_credits", 0) > 0:
        return {"allowed": True, "amount": 0, "source": "referral"}
    amount = PRICES[service]
    return {"allowed": float(account.get("balance") or 0) >= amount, "amount": amount,
        "source": "balance", "reason": "insufficient_balance"}


POLICY_TEXT = (
    "🎁 Har 5 ta yangi, kanalga a’zoligi tasdiqlangan do‘st uchun: "
    "bir oy amal qiladigan 5 ta bepul taqdimot va 1 ta bepul kurs ishi.\n"
    "Yana 5 ta yangi do‘st taklif qilib mukofotni qayta olish mumkin.\n\n"
    "📊 Bir oylik obuna — 25 000 so‘m, 10 ta taqdimot. "
    "Limit tugasa, yana 5 ta do‘st taklif qiling yoki har bir qo‘shimcha taqdimot uchun 10 000 so‘m to‘lang.\n"
    "📚 Kurs ishi — bepul mukofotdan so‘ng yana 5 ta do‘st taklif qiling yoki 30 000 so‘m to‘lang.\n"
    "📄 Referat / mustaqil ish — 8 000 so‘m. Maqola — 10 000 so‘m. "
    "Referat, maqola va kurs ishi DeepSeek R1 bilan yaratiladi.\n\n"
    "Obuna faqat taqdimotlarni qamrab oladi. Taklif mukofoti alohida qo‘shiladi. "
    "Obuna avtomatik yangilanmaydi; foydalanilmagan oylik taqdimot limiti muddat oxirida tugaydi."
)
