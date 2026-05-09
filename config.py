"""
config.py — Конфигурация бота.
Загружает переменные из .env файла и предоставляет их остальным модулям.
"""

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


class Config:
    # Токен Telegram бота
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Telegram ID администратора/мастера
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

    # Имя мастера для отображения в боте
    MASTER_NAME: str = os.getenv("MASTER_NAME", "Ваш мастер")

    # Максимум записей в день (0 = без ограничений)
    MAX_APPOINTMENTS_PER_DAY: int = int(os.getenv("MAX_APPOINTMENTS_PER_DAY", "10"))

    # Напоминание за N часов до записи
    REMINDER_HOURS_BEFORE: int = int(os.getenv("REMINDER_HOURS_BEFORE", "24"))

    # Путь к базе данных SQLite
    DB_PATH: str = "bot_database.db"

    # Часовой пояс
    TIMEZONE: str = "Europe/Kyiv"

    # ── Google Sheets інтеграція ──────────────────────────────────────────
    # ID таблиці (з URL: docs.google.com/spreadsheets/d/<SHEET_ID>/edit)
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

    # Шлях до JSON-ключа сервісного акаунту
    GOOGLE_CREDENTIALS: str = os.getenv("GOOGLE_CREDENTIALS", "google_credentials.json")

    @classmethod
    def google_sheets_enabled(cls) -> bool:
        """True якщо Google Sheets налаштовано."""
        import os as _os
        return bool(cls.GOOGLE_SHEET_ID) and _os.path.exists(cls.GOOGLE_CREDENTIALS)

    # Список услуг (название: длительность в минутах)
    SERVICES: dict = {
        "Наращивание ресниц (классика)": 90,
        "Наращивание ресниц (2D/3D)": 120,
        "Коррекция ресниц": 60,
        "Снятие ресниц": 30,
        "Ламинирование ресниц": 75,
    }

    # Статусы записей
    STATUS_PENDING = "pending"       # Ожидает подтверждения
    STATUS_CONFIRMED = "confirmed"   # Подтверждена
    STATUS_CANCELLED = "cancelled"   # Отменена
    STATUS_COMPLETED = "completed"   # Выполнена


# Проверка обязательных переменных
if not Config.BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в .env файле!")

if not Config.ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не задан в .env файле!")
