"""
bot.py — Точка входу. Запуск бота, реєстрація роутерів, планувальник задач.
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database import init_db
from handlers import (
    start_router, booking_router,
    my_appointments_router, admin_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    from database import get_appointments_for_reminder
    from utils.notifications import send_reminder
    reminders = await get_appointments_for_reminder(Config.REMINDER_HOURS_BEFORE)
    for apt in reminders:
        await send_reminder(bot, apt["user_telegram_id"], apt)
        logger.info(f"📩 Нагадування → {apt['user_telegram_id']}")


async def on_startup(bot: Bot):
    await init_db()
    logger.info("✅ База даних готова")

    # ── Google Sheets ──────────────────────────────────────────────────────
    gs_status = "вимкнено"
    if Config.google_sheets_enabled():
        from utils.google_sheets import init_google_sheets, sync_all_appointments
        from database import get_all_appointments

        ok = await init_google_sheets(Config.GOOGLE_CREDENTIALS, Config.GOOGLE_SHEET_ID)
        if ok:
            # Синхронізуємо всі існуючі записи при старті
            all_apts = await get_all_appointments(future_only=False)
            count = await sync_all_appointments(all_apts)
            gs_status = f"✅ підключено, синхронізовано {count} записів"
        else:
            gs_status = "⚠️ помилка підключення"
    else:
        logger.info("ℹ️ Google Sheets не налаштовано (GOOGLE_SHEET_ID порожній або credentials не знайдено)")

    # ── Повідомлення майстру ───────────────────────────────────────────────
    try:
        await bot.send_message(
            Config.ADMIN_ID,
            f"🚀 <b>Бот запущено!</b>\n"
            f"Майстер: {Config.MASTER_NAME}\n"
            f"Час: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📊 Google Sheets: {gs_status}\n\n"
            "Команди:\n"
            "/seed — демо-розклад\n"
            "/sync — синхронізувати Google Sheets\n"
            "/admin — панель управління",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не вдалося повідомити майстра: {e}")

    logger.info(f"🤖 Бот {Config.MASTER_NAME} запущено! Google Sheets: {gs_status}")


async def on_shutdown(bot: Bot):
    logger.info("🛑 Бот зупинено")


async def main():
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(booking_router)
    dp.include_router(my_appointments_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE)
    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=60,
        args=[bot],
        id="reminders",
        replace_existing=True
    )
    scheduler.start()
    logger.info("⏰ Планувальник нагадувань запущено")

    try:
        logger.info("🔄 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("👋 Сесію закрито")


if __name__ == "__main__":
    asyncio.run(main())
