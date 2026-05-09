"""
utils/notifications.py — Функції відправки сповіщень.
"""
import logging
from aiogram import Bot
from config import Config
from utils.helpers import format_date_ru

logger = logging.getLogger(__name__)


async def notify_admin_new_appointment(bot: Bot, apt: dict, user_telegram_id: int):
    date_str = format_date_ru(apt["date"])
    text = (
        "🔔 <b>Новий запис!</b>\n\n"
        f"👤 <b>Клієнт:</b> {apt.get('name', 'Не вказано')}\n"
        f"📞 <b>Телефон:</b> {apt.get('phone', 'Не вказано')}\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"🕐 <b>Час:</b> {apt['time']}\n"
        f"🆔 <b>ID запису:</b> #{apt['id']}\n"
        f"👤 <b>Telegram ID:</b> <code>{user_telegram_id}</code>"
    )
    try:
        await bot.send_message(Config.ADMIN_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не вдалося повідомити майстра: {e}")


async def notify_user_booking_confirmed(bot: Bot, telegram_id: int, apt: dict):
    date_str = format_date_ru(apt["date"])
    text = (
        "✅ <b>Запис підтверджено!</b>\n\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"🕐 <b>Час:</b> {apt['time']}\n\n"
        "Якщо потрібно скасувати — натисніть <b>📋 Мої записи</b> в меню.\n"
        f"З питань: ваш майстер {Config.MASTER_NAME}"
    )
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не вдалося повідомити клієнта {telegram_id}: {e}")


async def notify_admin_cancellation(bot: Bot, apt: dict):
    date_str = format_date_ru(apt["date"])
    text = (
        "❌ <b>Запис скасовано клієнтом</b>\n\n"
        f"👤 <b>Клієнт:</b> {apt.get('name', 'Не вказано')}\n"
        f"📞 <b>Телефон:</b> {apt.get('phone', 'Не вказано')}\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"🕐 <b>Час:</b> {apt['time']}"
    )
    try:
        await bot.send_message(Config.ADMIN_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не вдалося повідомити майстра про скасування: {e}")


async def send_reminder(bot: Bot, telegram_id: int, apt: dict):
    date_str = format_date_ru(apt["date"])
    hours = Config.REMINDER_HOURS_BEFORE
    if hours == 1:
        hours_text = "1 годину"
    elif hours < 5:
        hours_text = f"{hours} години"
    else:
        hours_text = f"{hours} годин"
    text = (
        f"⏰ <b>Нагадування про запис!</b>\n\n"
        f"Через {hours_text} у вас запис:\n\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"🕐 <b>Час:</b> {apt['time']}\n\n"
        "Чекаємо на вас! 💫"
    )
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не вдалося надіслати нагадування клієнту {telegram_id}: {e}")
