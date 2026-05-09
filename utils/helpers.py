"""
utils/helpers.py — Допоміжні функції.
"""
import re
from datetime import datetime

DAY_NAMES = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
DAY_NAMES_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTH_NAMES = [
    "", "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"
]


def format_date_ru(date_str: str) -> str:
    """'2024-01-15' → 'Понеділок, 15 січня 2024'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = DAY_NAMES[dt.weekday()]
    return f"{day_name}, {dt.day} {MONTH_NAMES[dt.month]} {dt.year}"


def format_date_short(date_str: str) -> str:
    """'2024-01-15' → '15 січ'"""
    month_short = ["", "січ", "лют", "бер", "квіт", "трав", "черв",
                   "лип", "серп", "вер", "жовт", "лист", "груд"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {month_short[dt.month]}"


def format_appointment(apt: dict, show_phone: bool = False) -> str:
    date_str = format_date_ru(apt["date"])
    status_icons = {
        "confirmed": "✅",
        "pending": "⏳",
        "cancelled": "❌",
        "completed": "✔️",
    }
    status_icon = status_icons.get(apt.get("status", ""), "❓")
    text = (
        f"{status_icon} <b>Запис #{apt['id']}</b>\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"🕐 <b>Час:</b> {apt['time']}\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
    )
    if apt.get("name"):
        text += f"👤 <b>Клієнт:</b> {apt['name']}\n"
    if show_phone and apt.get("phone"):
        text += f"📞 <b>Телефон:</b> {apt['phone']}\n"
    return text


def is_valid_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    pattern = r"^\+?[0-9]{10,15}$"
    return bool(re.match(pattern, cleaned))


def normalize_phone(phone: str) -> str:
    return re.sub(r"[\s\-\(\)]", "", phone)


def is_valid_name(name: str) -> bool:
    return len(name.strip()) >= 2
