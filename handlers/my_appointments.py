"""
handlers/my_appointments.py — Перегляд та скасування записів користувача.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import get_user_appointments, cancel_appointment, get_appointment_by_id
from keyboards import appointments_kb, cancel_appointment_kb, main_menu_kb
from utils.helpers import format_appointment, format_date_ru
from utils.notifications import notify_admin_cancellation

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📋 Мої записи")
async def my_appointments(message: Message, state: FSMContext):
    await state.clear()
    appointments = await get_user_appointments(message.from_user.id)
    if not appointments:
        await message.answer(
            "📋 <b>У вас немає активних записів.</b>\n\n"
            "Натисніть <b>📅 Записатись</b>, щоб записатись до майстра.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return
    text = f"📋 <b>Ваші записи ({len(appointments)}):</b>\n\n"
    for apt in appointments:
        text += format_appointment(apt) + "\n"
    text += "\n<i>Натисніть на запис, щоб скасувати його:</i>"
    await message.answer(text, reply_markup=appointments_kb(appointments), parse_mode="HTML")


@router.callback_query(F.data == "view_appointments")
async def view_appointments_callback(callback: CallbackQuery, state: FSMContext):
    appointments = await get_user_appointments(callback.from_user.id)
    if not appointments:
        await callback.message.edit_text(
            "📋 <b>У вас немає активних записів.</b>", parse_mode="HTML"
        )
        await callback.message.answer("🏠 Головне меню:", reply_markup=main_menu_kb())
        await callback.answer()
        return
    text = f"📋 <b>Ваші записи ({len(appointments)}):</b>\n\n"
    for apt in appointments:
        text += format_appointment(apt) + "\n"
    text += "\n<i>Натисніть на запис, щоб скасувати його:</i>"
    await callback.message.edit_text(text, reply_markup=appointments_kb(appointments), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_apt:"))
async def ask_cancel_appointment(callback: CallbackQuery, state: FSMContext):
    apt_id = int(callback.data.split(":")[1])
    apt = await get_appointment_by_id(apt_id)
    if not apt:
        await callback.answer("❌ Запис не знайдено", show_alert=True)
        return
    date_formatted = format_date_ru(apt["date"])
    await callback.message.edit_text(
        f"❓ <b>Ви хочете скасувати запис?</b>\n\n"
        f"💆 <b>Послуга:</b> {apt['service']}\n"
        f"📅 <b>Дата:</b> {date_formatted}\n"
        f"🕐 <b>Час:</b> {apt['time']}\n\n"
        "Цю дію не можна скасувати.",
        reply_markup=cancel_appointment_kb(apt_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_appointment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    apt_id = int(callback.data.split(":")[1])
    apt = await get_appointment_by_id(apt_id)
    success = await cancel_appointment(apt_id, callback.from_user.id)
    if not success:
        await callback.answer("❌ Не вдалося скасувати запис", show_alert=True)
        return
    await callback.message.edit_text(
        "✅ <b>Запис скасовано.</b>\n\n"
        "Якщо хочете записатись знову — натисніть <b>📅 Записатись</b>.",
        parse_mode="HTML"
    )
    await callback.message.answer("🏠 Головне меню:", reply_markup=main_menu_kb())
    if apt:
        await notify_admin_cancellation(bot, apt)

    # ── Google Sheets: оновити статус ────────────────────────────────
    try:
        from utils.google_sheets import update_appointment_status, is_connected
        if is_connected():
            await update_appointment_status(apt_id, "cancelled")
    except Exception as _gs_err:
        logger.warning(f"[GSheets] Не вдалося оновити статус: {_gs_err}")

    await callback.answer("✅ Запис скасовано")
