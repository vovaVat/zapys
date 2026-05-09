"""
handlers/booking.py — Повний процес запису клієнта.

Виправлені баги:
- back_to_time / back_to_name / back_to_date тепер мають хендлери в КОЖНОМУ стані
- notify_user_booking_confirmed викликається після підтвердження запису
- Use saved name / saved phone — кнопки швидкого вибору
- Contact sharing для телефону
- Коректне управління reply-клавіатурою (показ/приховування)
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import Config
from database import (
    get_available_dates, get_available_times,
    create_appointment, get_appointment_by_id,
    get_or_create_user, get_user_by_telegram_id
)
from states import BookingStates
from keyboards import (
    services_kb, dates_kb, times_kb,
    name_kb, phone_kb, phone_request_kb, remove_reply_kb,
    confirm_kb, main_menu_kb, back_kb
)
from utils.helpers import (
    format_date_ru, is_valid_phone, is_valid_name, normalize_phone
)
from utils.notifications import (
    notify_admin_new_appointment, notify_user_booking_confirmed
)

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────────────────────────────
# КРОК 1: Початок запису — вибір послуги
# ─────────────────────────────────────────────────────────────────────

@router.message(F.text == "📅 Записатись")
async def start_booking(message: Message, state: FSMContext):
    await state.clear()
    await get_or_create_user(message.from_user.id)
    await state.set_state(BookingStates.choosing_service)
    await message.answer(
        "💆 <b>Оберіть послугу:</b>",
        reply_markup=services_kb(Config.SERVICES),
        parse_mode="HTML"
    )


@router.callback_query(BookingStates.choosing_service, F.data.startswith("service:"))
async def service_chosen(callback: CallbackQuery, state: FSMContext):
    service_name = callback.data.split(":", 1)[1]
    if service_name not in Config.SERVICES:
        await callback.answer("❌ Послугу не знайдено", show_alert=True)
        return

    await state.update_data(service=service_name)
    dates = await get_available_dates(days_ahead=30)

    if not dates:
        await callback.message.edit_text(
            "😔 На жаль, немає доступних дат для запису.\n"
            "Спробуйте пізніше або зв'яжіться з майстром напряму.",
            reply_markup=back_kb("cancel_booking")
        )
        await callback.answer()
        return

    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        f"✅ Послуга: <b>{service_name}</b>\n\n"
        "📅 <b>Оберіть зручну дату:</b>",
        reply_markup=dates_kb(dates),
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────
# КРОК 2: Вибір дати
# ─────────────────────────────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_date, F.data.startswith("date:"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":", 1)[1]
    await state.update_data(date=date_str)

    times = await get_available_times(date_str)
    if not times:
        await callback.answer("❌ На цю дату немає вільних слотів", show_alert=True)
        dates = await get_available_dates(days_ahead=30)
        await callback.message.edit_text(
            "😔 На обрану дату немає вільного часу.\nОберіть іншу дату:",
            reply_markup=dates_kb(dates),
            parse_mode="HTML"
        )
        return

    date_formatted = format_date_ru(date_str)
    await state.set_state(BookingStates.choosing_time)
    await callback.message.edit_text(
        f"📅 <b>{date_formatted}</b>\n\n"
        "🕐 <b>Оберіть зручний час:</b>",
        reply_markup=times_kb(times, date_str),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_date, F.data == "back_to_service")
async def back_to_service_from_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.choosing_service)
    await callback.message.edit_text(
        "💆 <b>Оберіть послугу:</b>",
        reply_markup=services_kb(Config.SERVICES),
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────
# КРОК 3: Вибір часу
# ─────────────────────────────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_time, F.data.startswith("time:"))
async def time_chosen(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split(":", 1)[1]
    await state.update_data(time=time_str)

    # Перевіряємо чи є збережене ім'я
    user = await get_user_by_telegram_id(callback.from_user.id)
    saved_name = user.get("name") if user else None

    # Зберігаємо для можливого швидкого використання
    await state.update_data(saved_name=saved_name)

    await state.set_state(BookingStates.entering_name)

    if saved_name:
        text = (
            f"🕐 Час: <b>{time_str}</b>\n\n"
            f"👤 <b>Введіть ваше ім'я:</b>\n"
            f"<i>Або скористайтесь збереженим іменем:</i>"
        )
    else:
        text = (
            f"🕐 Час: <b>{time_str}</b>\n\n"
            "👤 <b>Введіть ваше ім'я:</b>"
        )

    await callback.message.edit_text(
        text,
        reply_markup=name_kb(saved_name),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data == "back_to_service_from_time")
async def back_to_service_from_time(callback: CallbackQuery, state: FSMContext):
    """Назад до списку послуг (з вибору часу)."""
    await state.set_state(BookingStates.choosing_service)
    await callback.message.edit_text(
        "💆 <b>Оберіть послугу:</b>",
        reply_markup=services_kb(Config.SERVICES),
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────
# КРОК 4: Введення імені
# ─────────────────────────────────────────────────────────────────────

@router.callback_query(BookingStates.entering_name, F.data == "use_saved_name")
async def use_saved_name_cb(callback: CallbackQuery, state: FSMContext):
    """Використати збережене ім'я без повторного введення."""
    data = await state.get_data()
    saved_name = data.get("saved_name", "")

    if not saved_name:
        await callback.answer("❌ Збереженого імені не знайдено", show_alert=True)
        return

    await state.update_data(name=saved_name)

    # Перевіряємо чи є збережений телефон
    user = await get_user_by_telegram_id(callback.from_user.id)
    saved_phone = user.get("phone") if user else None
    await state.update_data(saved_phone=saved_phone)

    await state.set_state(BookingStates.entering_phone)

    await callback.message.edit_text(
        f"👤 Ім'я: <b>{saved_name}</b>\n\n"
        "📞 <b>Введіть ваш номер телефону:</b>\n"
        "<i>Або скористайтесь збереженим / поділіться контактом</i>",
        reply_markup=phone_kb(saved_phone),
        parse_mode="HTML"
    )
    # Показуємо reply-клавіатуру для Contact sharing
    await callback.message.answer(
        "📲 Натисніть кнопку або введіть номер вручну:",
        reply_markup=phone_request_kb()
    )
    await callback.answer()


@router.callback_query(BookingStates.entering_name, F.data == "back_to_time")
async def back_to_time_from_name(callback: CallbackQuery, state: FSMContext):
    """
    ВИПРАВЛЕННЯ БАГА: повернення до вибору часу зі стану entering_name.
    Раніше цей callback ігнорувався — стан не збігався з фільтром.
    """
    data = await state.get_data()
    date_str = data.get("date")

    if date_str:
        times = await get_available_times(date_str)
        date_formatted = format_date_ru(date_str)
        await state.set_state(BookingStates.choosing_time)
        await callback.message.edit_text(
            f"📅 <b>{date_formatted}</b>\n\n"
            "🕐 <b>Оберіть зручний час:</b>",
            reply_markup=times_kb(times, date_str),
            parse_mode="HTML"
        )
    else:
        # Якщо дата не збережена — повертаємося до дат
        dates = await get_available_dates(days_ahead=30)
        await state.set_state(BookingStates.choosing_date)
        await callback.message.edit_text(
            "📅 <b>Оберіть зручну дату:</b>",
            reply_markup=dates_kb(dates),
            parse_mode="HTML"
        )
    await callback.answer()


@router.message(BookingStates.entering_name)
async def name_entered(message: Message, state: FSMContext):
    """Обробка введеного вручну імені."""
    name = message.text.strip() if message.text else ""

    if not is_valid_name(name):
        await message.answer(
            "❌ Ім'я занадто коротке. Введіть ваше ім'я (мінімум 2 символи):",
            parse_mode="HTML"
        )
        return

    await state.update_data(name=name)

    # Перевіряємо збережений телефон
    user = await get_user_by_telegram_id(message.from_user.id)
    saved_phone = user.get("phone") if user else None
    await state.update_data(saved_phone=saved_phone)

    await state.set_state(BookingStates.entering_phone)

    await message.answer(
        f"👤 Ім'я: <b>{name}</b>\n\n"
        "📞 <b>Введіть ваш номер телефону:</b>\n"
        "<i>Або скористайтесь збереженим / поділіться контактом</i>",
        reply_markup=phone_kb(saved_phone),
        parse_mode="HTML"
    )
    # Reply-клавіатура з Contact кнопкою
    await message.answer(
        "📲 Натисніть кнопку або введіть номер вручну:",
        reply_markup=phone_request_kb()
    )


# ─────────────────────────────────────────────────────────────────────
# КРОК 5: Введення телефону
# ─────────────────────────────────────────────────────────────────────

@router.callback_query(BookingStates.entering_phone, F.data == "use_saved_phone")
async def use_saved_phone_cb(callback: CallbackQuery, state: FSMContext):
    """Використати збережений номер телефону."""
    data = await state.get_data()
    saved_phone = data.get("saved_phone", "")

    if not saved_phone:
        await callback.answer("❌ Збереженого телефону не знайдено", show_alert=True)
        return

    await state.update_data(phone=saved_phone)
    await _show_confirmation(callback.message, state, remove_keyboard=True)
    await callback.answer()


@router.callback_query(BookingStates.entering_phone, F.data == "back_to_name")
async def back_to_name_from_phone(callback: CallbackQuery, state: FSMContext):
    """
    Повернення до введення імені зі стану entering_phone.
    Прибираємо reply-клавіатуру.
    """
    data = await state.get_data()
    saved_name = data.get("saved_name")

    await state.set_state(BookingStates.entering_name)
    # Видаляємо reply-клавіатуру
    await callback.message.answer(
        "👤 <b>Введіть ваше ім'я:</b>",
        reply_markup=remove_reply_kb(),
        parse_mode="HTML"
    )
    await callback.message.edit_text(
        "👤 <b>Введіть ваше ім'я:</b>",
        reply_markup=name_kb(saved_name),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(BookingStates.entering_phone, F.contact)
async def contact_shared(message: Message, state: FSMContext):
    """Обробка поділеного контакту (Contact sharing)."""
    contact = message.contact
    phone = normalize_phone(contact.phone_number)
    await state.update_data(phone=phone)

    # Прибираємо reply-клавіатуру і показуємо підтвердження
    await message.answer(
        "📞 Номер отримано.",
        reply_markup=remove_reply_kb()
    )
    await _show_confirmation(message, state, remove_keyboard=False)


@router.message(BookingStates.entering_phone)
async def phone_entered(message: Message, state: FSMContext):
    """Обробка введеного вручну номеру телефону."""
    phone = message.text.strip() if message.text else ""

    if not is_valid_phone(phone):
        await message.answer(
            "❌ Невірний формат телефону.\n"
            "Введіть номер у форматі: <b>+380991234567</b>\n"
            "<i>або скористайтесь кнопкою «📲 Поділитись номером»</i>",
            parse_mode="HTML"
        )
        return

    phone = normalize_phone(phone)
    await state.update_data(phone=phone)

    # Прибираємо reply-клавіатуру
    await message.answer("✅", reply_markup=remove_reply_kb())
    await _show_confirmation(message, state, remove_keyboard=False)


# ─────────────────────────────────────────────────────────────────────
# КРОК 6: Підтвердження запису
# ─────────────────────────────────────────────────────────────────────

async def _show_confirmation(
    message_or_target: Message,
    state: FSMContext,
    remove_keyboard: bool = False
):
    """Допоміжна функція: показати підсумок і попросити підтвердження."""
    data = await state.get_data()
    date_formatted = format_date_ru(data["date"])
    summary = (
        "📋 <b>Перевірте дані запису:</b>\n\n"
        f"💆 <b>Послуга:</b> {data['service']}\n"
        f"📅 <b>Дата:</b> {date_formatted}\n"
        f"🕐 <b>Час:</b> {data['time']}\n"
        f"👤 <b>Ім'я:</b> {data['name']}\n"
        f"📞 <b>Телефон:</b> {data['phone']}\n\n"
        "Все вірно?"
    )
    await state.set_state(BookingStates.confirming)

    if remove_keyboard:
        # Для callback — просто edit
        await message_or_target.edit_text(
            summary,
            reply_markup=confirm_kb(),
            parse_mode="HTML"
        )
    else:
        # Для Message — новий answer
        await message_or_target.answer(
            summary,
            reply_markup=confirm_kb(),
            parse_mode="HTML"
        )


@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    from database import update_user
    await update_user(callback.from_user.id, data["name"], data["phone"])

    apt_id = await create_appointment(
        telegram_id=callback.from_user.id,
        date_str=data["date"],
        time_str=data["time"],
        service=data["service"]
    )

    if not apt_id:
        await callback.message.edit_text(
            "😔 <b>На жаль, цей час вже зайнятий.</b>\n\n"
            "Будь ласка, розпочніть запис знову та оберіть інший час.",
            reply_markup=back_kb("cancel_booking"),
            parse_mode="HTML"
        )
        await callback.answer("❌ Час вже зайнято")
        return

    apt = await get_appointment_by_id(apt_id)
    # Доповнюємо поточними даними (ім'я/телефон ще не в БД до refresh)
    if apt:
        apt["name"] = data["name"]
        apt["phone"] = data["phone"]

    date_formatted = format_date_ru(data["date"])

    # Підтвердження для клієнта
    await callback.message.edit_text(
        "🎉 <b>Запис успішно створено!</b>\n\n"
        f"💆 <b>Послуга:</b> {data['service']}\n"
        f"📅 <b>Дата:</b> {date_formatted}\n"
        f"🕐 <b>Час:</b> {data['time']}\n\n"
        "Майстер отримав сповіщення. До зустрічі! 😊",
        parse_mode="HTML"
    )
    await callback.message.answer("🏠 Головне меню:", reply_markup=main_menu_kb())

    # Сповіщення адміна про новий запис
    if apt:
        await notify_admin_new_appointment(bot, apt, callback.from_user.id)

    # Підтвердження клієнту (окреме повідомлення з деталями)
    await notify_user_booking_confirmed(bot, callback.from_user.id, apt or data)

    # ── Google Sheets: синхронізувати новий запис ─────────────────────
    try:
        from utils.google_sheets import add_appointment as gs_add, is_connected
        if is_connected() and apt:
            apt_gs = dict(apt)
            apt_gs["user_telegram_id"] = callback.from_user.id
            await gs_add(apt_gs)
    except Exception as _gs_err:
        logger.warning(f"[GSheets] Не вдалося додати запис: {_gs_err}")

    await state.clear()
    await callback.answer("✅ Запис створено!")


@router.callback_query(BookingStates.confirming, F.data == "edit_booking")
async def edit_booking(callback: CallbackQuery, state: FSMContext):
    """Редагувати — повернутись до вибору послуги."""
    await state.set_state(BookingStates.choosing_service)
    await callback.message.edit_text(
        "💆 <b>Оберіть послугу:</b>",
        reply_markup=services_kb(Config.SERVICES),
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────
# Скасування запису на будь-якому кроці
# ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Запис скасовано.\n\nПовертаємось до головного меню."
    )
    await callback.message.answer("🏠 Головне меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Повернення до головного меню.")
    await callback.message.answer("Головне меню:", reply_markup=main_menu_kb())
    await callback.answer()
