"""
keyboards/user_kb.py — Клавіатури для користувацького інтерфейсу.
"""
from aiogram.types import (
    InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import datetime


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📅 Записатись"),
        KeyboardButton(text="📋 Мої записи"),
    )
    builder.row(
        KeyboardButton(text="ℹ️ Про майстра"),
        KeyboardButton(text="📞 Контакти"),
    )
    return builder.as_markup(resize_keyboard=True)


def services_kb(services: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service_name, duration in services.items():
        builder.button(
            text=f"💆 {service_name} ({duration} хв)",
            callback_data=f"service:{service_name}"
        )
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def dates_kb(dates: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for date_str in dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        month_names = ["", "січ", "лют", "бер", "квіт", "трав", "черв",
                       "лип", "серп", "вер", "жовт", "лист", "груд"]
        label = f"{day_names[dt.weekday()]}, {dt.day} {month_names[dt.month]}"
        builder.button(text=label, callback_data=f"date:{date_str}")
    builder.button(text="◀️ Назад", callback_data="back_to_service")
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(2)
    return builder.as_markup()


def times_kb(times: list, date_str: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in times:
        builder.button(text=f"🕐 {t}", callback_data=f"time:{t}")
    builder.button(text="◀️ Назад", callback_data="back_to_service_from_time")
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(3)
    return builder.as_markup()


def name_kb(saved_name: str | None = None) -> InlineKeyboardMarkup:
    """
    Клавіатура для кроку введення імені.
    Якщо є збережене ім'я — показує кнопку швидкого використання.
    """
    builder = InlineKeyboardBuilder()
    if saved_name:
        display = saved_name[:25] + ("…" if len(saved_name) > 25 else "")
        builder.button(
            text=f"💾 Використати: {display}",
            callback_data="use_saved_name"
        )
    builder.button(text="◀️ Назад", callback_data="back_to_time")
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def phone_kb(saved_phone: str | None = None) -> InlineKeyboardMarkup:
    """
    Inline-клавіатура для кроку введення телефону.
    Якщо є збережений телефон — показує кнопку швидкого використання.
    """
    builder = InlineKeyboardBuilder()
    if saved_phone:
        builder.button(
            text=f"💾 Використати: {saved_phone}",
            callback_data="use_saved_phone"
        )
    builder.button(text="◀️ Назад", callback_data="back_to_name")
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def phone_request_kb() -> ReplyKeyboardMarkup:
    """
    Reply-клавіатура з кнопкою «Поділитись номером» (Contact).
    Відображається під час введення телефону.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="📲 Поділитись номером", request_contact=True)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_reply_kb() -> ReplyKeyboardRemove:
    """Прибрати reply-клавіатуру."""
    return ReplyKeyboardRemove()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити запис", callback_data="confirm_booking")
    builder.button(text="✏️ Змінити", callback_data="edit_booking")
    builder.button(text="❌ Скасувати", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def appointments_kb(appointments: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for apt in appointments:
        dt = datetime.strptime(apt["date"], "%Y-%m-%d")
        month_names = ["", "січ", "лют", "бер", "квіт", "трав", "черв",
                       "лип", "серп", "вер", "жовт", "лист", "груд"]
        date_label = f"{dt.day} {month_names[dt.month]}"
        builder.button(
            text=f"❌ {date_label} {apt['time']} — {apt['service'][:20]}",
            callback_data=f"cancel_apt:{apt['id']}"
        )
    builder.button(text="◀️ Назад до меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def cancel_appointment_kb(appointment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, скасувати", callback_data=f"confirm_cancel:{appointment_id}")
    builder.button(text="◀️ Ні, назад", callback_data="view_appointments")
    builder.adjust(1)
    return builder.as_markup()


def back_kb(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=callback_data)
    return builder.as_markup()
