"""
utils/google_sheets.py — Інтеграція з Google Sheets.

Принцип: Google Sheets — ДЗЕРКАЛО SQLite.
Якщо Google Sheets недоступний — бот продовжує працювати нормально.
Всі помилки логуються але не зупиняють бота.

Структура таблиці "Записи":
  A: ID       B: Дата      C: Час       D: Послуга
  E: Клієнт  F: Телефон   G: Статус    H: Створено   I: Telegram ID

Структура таблиці "Розклад":
  Автоматично оновлюється при додаванні/закритті слотів
"""

import logging
import asyncio
from datetime import datetime
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальний клієнт (ініціалізується один раз при старті)
_gc = None
_spreadsheet = None
_appointments_sheet = None

SHEET_APPOINTMENTS = "Записи"
SHEET_SCHEDULE     = "Розклад"

# Заголовки таблиці записів
HEADERS_APPOINTMENTS = [
    "ID", "Дата", "Час", "Послуга",
    "Клієнт", "Телефон", "Статус", "Створено", "Telegram ID"
]

STATUS_MAP = {
    "confirmed": "✅ Підтверджено",
    "cancelled":  "❌ Скасовано",
    "completed":  "✔️ Виконано",
    "pending":    "⏳ Очікує",
}


def _safe(func):
    """Декоратор: перехоплює всі помилки Google Sheets, щоб не ламати бота."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"[Google Sheets] {func.__name__} помилка: {e}")
            return None
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# ІНІЦІАЛІЗАЦІЯ
# ─────────────────────────────────────────────────────────────────────────────

async def init_google_sheets(credentials_path: str, sheet_id: str) -> bool:
    """
    Ініціалізує підключення до Google Sheets.
    Викликати один раз при старті бота.
    Повертає True якщо підключення успішне.
    """
    global _gc, _spreadsheet, _appointments_sheet

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        # gspread синхронний — запускаємо в executor
        loop = asyncio.get_event_loop()
        _gc = await loop.run_in_executor(None, lambda: gspread.authorize(creds))
        _spreadsheet = await loop.run_in_executor(
            None, lambda: _gc.open_by_key(sheet_id)
        )

        # Підготовка аркушів
        await _ensure_sheets()
        logger.info("✅ Google Sheets підключено успішно")
        return True

    except ImportError:
        logger.warning("⚠️ gspread не встановлено. Google Sheets вимкнено.")
        return False
    except FileNotFoundError:
        logger.warning(f"⚠️ Файл credentials не знайдено: {credentials_path}")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Google Sheets не підключено: {e}")
        return False


async def _ensure_sheets():
    """Створює аркуші і заголовки якщо їх немає."""
    if not _spreadsheet:
        return

    loop = asyncio.get_event_loop()

    # Аркуш "Записи"
    existing = await loop.run_in_executor(
        None, lambda: [s.title for s in _spreadsheet.worksheets()]
    )

    if SHEET_APPOINTMENTS not in existing:
        ws = await loop.run_in_executor(
            None, lambda: _spreadsheet.add_worksheet(SHEET_APPOINTMENTS, rows=1000, cols=10)
        )
        await loop.run_in_executor(None, lambda: ws.append_row(HEADERS_APPOINTMENTS))
        # Форматуємо заголовок (жирний)
        await _format_header(ws, len(HEADERS_APPOINTMENTS))
        logger.info(f"✅ Аркуш '{SHEET_APPOINTMENTS}' створено")
    else:
        # Перевіряємо чи є заголовки
        ws = await loop.run_in_executor(
            None, lambda: _spreadsheet.worksheet(SHEET_APPOINTMENTS)
        )
        row1 = await loop.run_in_executor(None, lambda: ws.row_values(1))
        if not row1:
            await loop.run_in_executor(None, lambda: ws.insert_row(HEADERS_APPOINTMENTS, 1))


async def _format_header(ws, num_cols: int):
    """Форматує перший рядок: жирний, синій фон."""
    try:
        import gspread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: ws.format(
            f"A1:{chr(64 + num_cols)}1",
            {
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "backgroundColor": {"red": 0.122, "green": 0.290, "blue": 0.490},
                "horizontalAlignment": "CENTER"
            }
        ))
    except Exception:
        pass  # Форматування не критичне


def is_connected() -> bool:
    """Перевірити чи підключено Google Sheets."""
    return _spreadsheet is not None


# ─────────────────────────────────────────────────────────────────────────────
# ОПЕРАЦІЇ З ЗАПИСАМИ
# ─────────────────────────────────────────────────────────────────────────────

@_safe
async def add_appointment(apt: dict) -> Optional[int]:
    """
    Додати новий запис у Google Sheets.
    apt — словник з полями: id, date, time, service, name, phone, status, created_at, user_telegram_id
    Повертає номер рядка або None.
    """
    if not _spreadsheet:
        return None

    loop = asyncio.get_event_loop()
    ws = await loop.run_in_executor(
        None, lambda: _spreadsheet.worksheet(SHEET_APPOINTMENTS)
    )

    # Форматуємо дату для відображення
    try:
        dt = datetime.strptime(apt.get("date", ""), "%Y-%m-%d")
        date_display = dt.strftime("%d.%m.%Y")
    except ValueError:
        date_display = apt.get("date", "")

    created_at = apt.get("created_at", "")
    if created_at:
        try:
            dt2 = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
            created_at = dt2.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    row = [
        apt.get("id", ""),
        date_display,
        apt.get("time", ""),
        apt.get("service", ""),
        apt.get("name", ""),
        apt.get("phone", ""),
        STATUS_MAP.get(apt.get("status", "confirmed"), "✅ Підтверджено"),
        created_at,
        str(apt.get("user_telegram_id", apt.get("telegram_id", ""))),
    ]

    await loop.run_in_executor(None, lambda: ws.append_row(row, value_input_option="USER_ENTERED"))

    # Підсвічуємо новий рядок зеленим
    all_rows = await loop.run_in_executor(None, ws.get_all_values)
    row_num = len(all_rows)
    await _color_row(ws, row_num, "confirmed")

    logger.info(f"[Google Sheets] Запис #{apt.get('id')} додано (рядок {row_num})")
    return row_num


@_safe
async def update_appointment_status(apt_id: int, new_status: str) -> bool:
    """
    Оновити статус запису в Google Sheets.
    Знаходить рядок по ID (колонка A) і оновлює колонку G (Статус).
    """
    if not _spreadsheet:
        return False

    loop = asyncio.get_event_loop()
    ws = await loop.run_in_executor(
        None, lambda: _spreadsheet.worksheet(SHEET_APPOINTMENTS)
    )

    # Шукаємо рядок з потрібним ID
    cell = await loop.run_in_executor(
        None, lambda: ws.find(str(apt_id), in_column=1)
    )
    if not cell:
        logger.warning(f"[Google Sheets] Запис #{apt_id} не знайдено в таблиці")
        return False

    row_num = cell.row
    status_display = STATUS_MAP.get(new_status, new_status)

    # Оновлюємо колонку G (статус)
    await loop.run_in_executor(
        None, lambda: ws.update_cell(row_num, 7, status_display)
    )
    # Міняємо колір рядка
    await _color_row(ws, row_num, new_status)

    logger.info(f"[Google Sheets] Запис #{apt_id} → статус: {status_display}")
    return True


@_safe
async def _color_row(ws, row_num: int, status: str):
    """Підсвічує рядок кольором залежно від статусу."""
    colors = {
        "confirmed": {"red": 0.851, "green": 0.918, "blue": 0.827},   # світло-зелений
        "cancelled": {"red": 0.957, "green": 0.800, "blue": 0.800},   # світло-червоний
        "completed": {"red": 0.812, "green": 0.886, "blue": 0.953},   # світло-синій
    }
    color = colors.get(status, {"red": 1, "green": 1, "blue": 1})
    cols = len(HEADERS_APPOINTMENTS)
    end_col = chr(64 + cols)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: ws.format(
        f"A{row_num}:{end_col}{row_num}",
        {"backgroundColor": color}
    ))


@_safe
async def sync_all_appointments(appointments: list) -> int:
    """
    Повна синхронізація — перезаписує всю таблицю записів.
    Використовується при старті бота або команді /sync.
    Повертає кількість записів.
    """
    if not _spreadsheet:
        return 0

    loop = asyncio.get_event_loop()
    ws = await loop.run_in_executor(
        None, lambda: _spreadsheet.worksheet(SHEET_APPOINTMENTS)
    )

    # Очищуємо таблицю (крім заголовка)
    last_row = max(len(appointments) + 2, 10)
    await loop.run_in_executor(
        None, lambda: ws.batch_clear([f"A2:I{last_row}"])
    )

    if not appointments:
        return 0

    rows = []
    for apt in appointments:
        try:
            dt = datetime.strptime(apt.get("date", ""), "%Y-%m-%d")
            date_display = dt.strftime("%d.%m.%Y")
        except ValueError:
            date_display = apt.get("date", "")

        created_at = apt.get("created_at", "")
        try:
            dt2 = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
            created_at = dt2.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

        rows.append([
            apt.get("id", ""),
            date_display,
            apt.get("time", ""),
            apt.get("service", ""),
            apt.get("name", ""),
            apt.get("phone", ""),
            STATUS_MAP.get(apt.get("status", ""), apt.get("status", "")),
            created_at,
            str(apt.get("user_telegram_id", apt.get("telegram_id", ""))),
        ])

    await loop.run_in_executor(
        None, lambda: ws.update(f"A2:I{len(rows) + 1}", rows)
    )

    # Форматуємо кольори
    for i, apt in enumerate(appointments, start=2):
        await _color_row(ws, i, apt.get("status", "confirmed"))

    logger.info(f"[Google Sheets] Синхронізовано {len(rows)} записів")
    return len(rows)
