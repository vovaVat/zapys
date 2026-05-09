"""
database.py — Работа с базой данных SQLite.
Все асинхронные операции с БД через aiosqlite.
Таблицы: users, appointments, schedule
"""

import aiosqlite
import logging
from datetime import datetime, date, timedelta
from config import Config

logger = logging.getLogger(__name__)


async def init_db():
    """Инициализация БД: создание таблиц если не существуют."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name        TEXT,
                phone       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # Таблица записей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                date        TEXT NOT NULL,
                time        TEXT NOT NULL,
                service     TEXT NOT NULL,
                status      TEXT DEFAULT 'confirmed',
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Таблица расписания (доступные слоты)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL,
                time         TEXT NOT NULL,
                is_available INTEGER DEFAULT 1,
                UNIQUE(date, time)
            )
        """)

        await db.commit()
        logger.info("✅ База данных инициализирована")


# ────────────────────────── USERS ──────────────────────────

async def get_or_create_user(telegram_id: int) -> dict | None:
    """Получить пользователя по telegram_id или создать нового."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        # Создаём нового пользователя
        await db.execute(
            "INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,)
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_user(telegram_id: int, name: str, phone: str):
    """Обновить имя и телефон пользователя."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET name = ?, phone = ? WHERE telegram_id = ?",
            (name, phone, telegram_id)
        )
        await db.commit()


async def get_user_by_telegram_id(telegram_id: int) -> dict | None:
    """Получить пользователя по telegram_id."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ────────────────────────── APPOINTMENTS ──────────────────────────

async def create_appointment(
    telegram_id: int,
    date_str: str,
    time_str: str,
    service: str
) -> int | None:
    """
    Создать запись. Возвращает ID созданной записи или None при ошибке.
    Проверяет: слот свободен, не превышен дневной лимит.
    """
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Получаем ID пользователя
        async with db.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            user = await cursor.fetchone()
            if not user:
                return None
            user_id = user["id"]

        # Проверка: слот существует и доступен
        async with db.execute(
            "SELECT * FROM schedule WHERE date = ? AND time = ? AND is_available = 1",
            (date_str, time_str)
        ) as cursor:
            slot = await cursor.fetchone()
            if not slot:
                return None

        # Проверка: слот уже не занят
        async with db.execute(
            """SELECT id FROM appointments
               WHERE date = ? AND time = ? AND status != 'cancelled'""",
            (date_str, time_str)
        ) as cursor:
            existing = await cursor.fetchone()
            if existing:
                return None

        # Проверка дневного лимита
        if Config.MAX_APPOINTMENTS_PER_DAY > 0:
            async with db.execute(
                """SELECT COUNT(*) as cnt FROM appointments
                   WHERE date = ? AND status != 'cancelled'""",
                (date_str,)
            ) as cursor:
                row = await cursor.fetchone()
                if row["cnt"] >= Config.MAX_APPOINTMENTS_PER_DAY:
                    return None

        # Создаём запись
        cursor = await db.execute(
            """INSERT INTO appointments (user_id, date, time, service, status)
               VALUES (?, ?, ?, ?, 'confirmed')""",
            (user_id, date_str, time_str, service)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_appointments(telegram_id: int) -> list[dict]:
    """Получить все актуальные (не отменённые) записи пользователя."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = date.today().isoformat()
        async with db.execute(
            """SELECT a.*, u.name, u.phone FROM appointments a
               JOIN users u ON a.user_id = u.id
               WHERE u.telegram_id = ? AND a.status != 'cancelled'
               AND a.date >= ?
               ORDER BY a.date, a.time""",
            (telegram_id, today)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def cancel_appointment(appointment_id: int, telegram_id: int) -> bool:
    """Отменить запись. Возвращает True при успехе."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        # Проверяем что запись принадлежит этому пользователю
        async with db.execute(
            """SELECT a.id FROM appointments a
               JOIN users u ON a.user_id = u.id
               WHERE a.id = ? AND u.telegram_id = ?""",
            (appointment_id, telegram_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False

        await db.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,)
        )
        await db.commit()
        return True


async def get_all_appointments(future_only: bool = False) -> list[dict]:
    """Получить все записи (для админа)."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT a.*, u.name, u.phone, u.telegram_id as user_telegram_id
            FROM appointments a
            JOIN users u ON a.user_id = u.id
            WHERE a.status != 'cancelled'
        """
        params = []
        if future_only:
            query += " AND a.date >= ?"
            params.append(date.today().isoformat())
        query += " ORDER BY a.date, a.time"

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def admin_cancel_appointment(appointment_id: int) -> bool:
    """Отменить запись (для админа, без проверки владельца)."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,)
        )
        await db.commit()
        return True


async def get_appointment_by_id(appointment_id: int) -> dict | None:
    """Получить запись по ID."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT a.*, u.name, u.phone, u.telegram_id as user_telegram_id
               FROM appointments a
               JOIN users u ON a.user_id = u.id
               WHERE a.id = ?""",
            (appointment_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_appointments_for_reminder(hours_before: int) -> list[dict]:
    """
    Получить записи, до которых осталось примерно hours_before часов.
    Используется для напоминаний.
    """
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = datetime.now() + timedelta(hours=hours_before)
        target_date = target.strftime("%Y-%m-%d")
        target_time = target.strftime("%H:%M")

        async with db.execute(
            """SELECT a.*, u.name, u.telegram_id as user_telegram_id
               FROM appointments a
               JOIN users u ON a.user_id = u.id
               WHERE a.date = ? AND a.time = ? AND a.status = 'confirmed'""",
            (target_date, target_time)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ────────────────────────── SCHEDULE ──────────────────────────

async def get_available_dates(days_ahead: int = 30) -> list[str]:
    """Получить список дат с доступными слотами на ближайшие N дней."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = date.today().isoformat()
        limit = (date.today() + timedelta(days=days_ahead)).isoformat()

        async with db.execute(
            """SELECT DISTINCT s.date FROM schedule s
               WHERE s.date >= ? AND s.date <= ? AND s.is_available = 1
               AND NOT EXISTS (
                   SELECT 1 FROM appointments a
                   WHERE a.date = s.date AND a.time = s.time
                   AND a.status != 'cancelled'
               )
               ORDER BY s.date""",
            (today, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r["date"] for r in rows]


async def get_available_times(date_str: str) -> list[str]:
    """Получить доступные временные слоты на конкретную дату."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.time FROM schedule s
               WHERE s.date = ? AND s.is_available = 1
               AND NOT EXISTS (
                   SELECT 1 FROM appointments a
                   WHERE a.date = s.date AND a.time = s.time
                   AND a.status != 'cancelled'
               )
               ORDER BY s.time""",
            (date_str,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r["time"] for r in rows]


async def add_schedule_slot(date_str: str, time_str: str) -> bool:
    """Добавить слот в расписание. Возвращает False если уже существует."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO schedule (date, time, is_available) VALUES (?, ?, 1)",
                (date_str, time_str)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Слот уже существует
            await db.execute(
                "UPDATE schedule SET is_available = 1 WHERE date = ? AND time = ?",
                (date_str, time_str)
            )
            await db.commit()
            return True


async def remove_schedule_slot(date_str: str, time_str: str) -> bool:
    """Удалить/закрыть слот из расписания."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute(
            "UPDATE schedule SET is_available = 0 WHERE date = ? AND time = ?",
            (date_str, time_str)
        )
        await db.commit()
        return True


async def get_schedule_for_date(date_str: str) -> list[dict]:
    """Получить всё расписание на дату (для админа)."""
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM schedule WHERE date = ? ORDER BY time",
            (date_str,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def generate_week_schedule(
    start_date: date,
    work_days: list[int],   # 0=пн .. 6=вс
    time_slots: list[str]   # ['09:00', '10:00', ...]
) -> int:
    """
    Сгенерировать расписание на 7 дней вперёд.
    Возвращает количество добавленных слотов.
    """
    count = 0
    async with aiosqlite.connect(Config.DB_PATH) as db:
        for i in range(7):
            current = start_date + timedelta(days=i)
            if current.weekday() in work_days:
                for t in time_slots:
                    try:
                        await db.execute(
                            "INSERT OR IGNORE INTO schedule (date, time, is_available) VALUES (?, ?, 1)",
                            (current.isoformat(), t)
                        )
                        count += 1
                    except Exception:
                        pass
        await db.commit()
    return count


async def get_week_full_schedule(start_date: date, days: int = 7) -> dict:
    """
    Повертає повне розкладу на N днів починаючи з start_date.
    Структура: {
        'YYYY-MM-DD': {
            'slots': [
                {
                    'time': '09:00',
                    'is_available': 1,
                    'booked': False,
                    'appointment': None   # або dict із записом
                },
                ...
            ]
        },
        ...
    }
    """
    result = {}
    end_date = start_date + timedelta(days=days - 1)

    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Усі слоти в діапазоні
        async with db.execute(
            """SELECT * FROM schedule
               WHERE date >= ? AND date <= ?
               ORDER BY date, time""",
            (start_date.isoformat(), end_date.isoformat())
        ) as cursor:
            all_slots = [dict(r) for r in await cursor.fetchall()]

        # Усі підтверджені записи в діапазоні
        async with db.execute(
            """SELECT a.*, u.name, u.phone, u.telegram_id as user_telegram_id
               FROM appointments a
               JOIN users u ON a.user_id = u.id
               WHERE a.date >= ? AND a.date <= ?
               AND a.status != 'cancelled'
               ORDER BY a.date, a.time""",
            (start_date.isoformat(), end_date.isoformat())
        ) as cursor:
            all_apts = [dict(r) for r in await cursor.fetchall()]

    # Індекс записів по (дата, час)
    apt_index = {(a["date"], a["time"]): a for a in all_apts}

    for slot in all_slots:
        d = slot["date"]
        t = slot["time"]
        apt = apt_index.get((d, t))
        slot_info = {
            "time": t,
            "is_available": slot["is_available"],
            "booked": apt is not None,
            "appointment": apt
        }
        if d not in result:
            result[d] = {"slots": []}
        result[d]["slots"].append(slot_info)

    return result


async def seed_demo_data():
    """
    Заполнить БД тестовыми данными для демонстрации.
    Добавляет расписание на ближайшие 14 дней.
    """
    from datetime import date, timedelta
    today = date.today()
    work_days = [0, 1, 2, 3, 4]  # Пн-Пт
    time_slots = [
        "09:00", "10:00", "11:00", "12:00",
        "13:00", "14:00", "15:00", "16:00", "17:00"
    ]

    count = 0
    async with aiosqlite.connect(Config.DB_PATH) as db:
        for day_offset in range(14):
            current = today + timedelta(days=day_offset)
            if current.weekday() in work_days:
                for t in time_slots:
                    try:
                        await db.execute(
                            "INSERT OR IGNORE INTO schedule (date, time, is_available) VALUES (?, ?, 1)",
                            (current.isoformat(), t)
                        )
                        count += 1
                    except Exception:
                        pass
        await db.commit()

    logger.info(f"✅ Демо-данные добавлены: {count} слотов расписания")
    return count
