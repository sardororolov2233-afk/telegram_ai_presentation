"""
Bot Database Helper
==================
Bot'ning bot_database.db dan balans o'qish uchun yordamchi funksiyalar.
Backend app bu funksiyalarni ishlatib, foydalanuvchi balansini bot bazasidan oladi.
"""
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

# Bot database yo'li
BOT_DB_PATH = os.getenv("BOT_DB_PATH", r"D:\telegram_bot\bot_database.db")


def get_bot_user_balance(telegram_id: int) -> int:
    """Bot bazasidan (referat_users) foydalanuvchi balansini olish."""
    try:
        conn = sqlite3.connect(BOT_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM referat_users WHERE user_id = ?", (telegram_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"Bot DB balans olishda xato (tg:{telegram_id}): {e}")
        return 0
