"""
keyboards/admin_kb.py — Клавіатури для панелі адміністратора.
"""
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import datetime


def admin_main_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📅 Тиждень"),
        KeyboardButton(text="📊 Excel"),
    )
    builder.row(
        KeyboardButton(text="📋 Всі записи"),
        KeyboardButton(text="📅 Розклад"),
    )
    builder.row(
        KeyboardButton(text="➕ Додати слоти"),
        KeyboardButton(text="🗓 Згенерувати тиждень"),
    )
    builder.row(
        KeyboardButton(text="👤 Режим клієнта"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_schedule_kb(date_str: str, slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        t = slot["time"]
        if slot["is_available"]:
            builder.button(text=f"✅ {t}", callback_data=f"admin_remove_slot:{date_str}:{t}")
        else:
            builder.button(text=f"❌ {t} (закрито)", callback_data=f"admin_open_slot:{date_str}:{t}")
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(3)
    return builder.as_markup()


def admin_appointments_kb(appointments: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for apt in appointments:
        dt = datetime.strptime(apt["date"], "%Y-%m-%d")
        month_names = ["", "січ", "лют", "бер", "квіт", "трав", "черв",
                       "лип", "серп", "вер", "жовт", "лист", "груд"]
        date_label = f"{dt.day} {month_names[dt.month]}"
        name = apt.get("name") or "Без імені"
        builder.button(
            text=f"🗑 {date_label} {apt['time']} | {name[:15]}",
            callback_data=f"admin_cancel_apt:{apt['id']}"
        )
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def admin_cancel_appointment_kb(appointment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Видалити запис", callback_data=f"admin_confirm_cancel:{appointment_id}")
    builder.button(text="◀️ Скасувати", callback_data="admin_view_appointments")
    builder.adjust(1)
    return builder.as_markup()


def admin_generate_week_kb() -> InlineKeyboardMarkup:
    """Підтвердження генерації розкладу на тиждень — кнопками."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, згенерувати", callback_data="admin_confirm_gen_week")
    builder.button(text="❌ Скасувати", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()
