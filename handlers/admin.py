"""
handlers/admin.py — Панель адміністратора/майстра.
"""
import io
import logging
from datetime import datetime, date, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from config import Config
from database import (
    get_all_appointments, admin_cancel_appointment,
    get_appointment_by_id, add_schedule_slot,
    remove_schedule_slot, get_schedule_for_date,
    generate_week_schedule, get_available_dates,
    seed_demo_data, get_week_full_schedule
)
from states import AdminStates
from keyboards import (
    admin_main_kb, admin_schedule_kb,
    admin_appointments_kb, admin_cancel_appointment_kb,
    admin_generate_week_kb, main_menu_kb, back_kb
)
from utils.helpers import format_appointment, format_date_ru
from utils.excel_export import generate_week_excel

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("🚫 Немає доступу.")
        return
    await state.clear()
    await message.answer(
        "🧑‍💼 <b>Панель адміністратора</b>\n\n"
        f"Майстер: {Config.MASTER_NAME}",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "📋 Всі записи")
async def admin_all_appointments(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    appointments = await get_all_appointments(future_only=True)
    if not appointments:
        await message.answer(
            "📋 <b>Немає майбутніх записів.</b>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )
        return
    text = f"📋 <b>Всі записи ({len(appointments)}):</b>\n\n"
    for apt in appointments:
        text += format_appointment(apt, show_phone=True)
        text += "─────────────\n"
    await message.answer(text, reply_markup=admin_appointments_kb(appointments), parse_mode="HTML")


@router.callback_query(F.data == "admin_view_appointments")
async def admin_view_appointments_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    appointments = await get_all_appointments(future_only=True)
    if not appointments:
        await callback.message.edit_text("📋 <b>Немає майбутніх записів.</b>", parse_mode="HTML")
        await callback.answer()
        return
    text = f"📋 <b>Всі записи ({len(appointments)}):</b>\n\n"
    for apt in appointments:
        text += format_appointment(apt, show_phone=True)
        text += "─────────────\n"
    await callback.message.edit_text(text, reply_markup=admin_appointments_kb(appointments), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cancel_apt:"))
async def admin_ask_cancel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    apt_id = int(callback.data.split(":")[1])
    apt = await get_appointment_by_id(apt_id)
    if not apt:
        await callback.answer("❌ Запис не знайдено", show_alert=True)
        return
    date_formatted = format_date_ru(apt["date"])
    await callback.message.edit_text(
        f"🗑 <b>Видалити запис?</b>\n\n"
        f"👤 Клієнт: {apt.get('name', 'Не вказано')}\n"
        f"📞 Телефон: {apt.get('phone', 'Не вказано')}\n"
        f"💆 Послуга: {apt['service']}\n"
        f"📅 Дата: {date_formatted}\n"
        f"🕐 Час: {apt['time']}",
        reply_markup=admin_cancel_appointment_kb(apt_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_cancel:"))
async def admin_confirm_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    apt_id = int(callback.data.split(":")[1])
    apt = await get_appointment_by_id(apt_id)
    user_telegram_id = apt.get("user_telegram_id") if apt else None
    await admin_cancel_appointment(apt_id)
    await callback.message.edit_text("✅ <b>Запис видалено.</b>", parse_mode="HTML")
    await callback.message.answer("🧑‍💼 Панель адміністратора:", reply_markup=admin_main_kb())

    # ── Google Sheets: оновити статус ────────────────────────────────
    try:
        from utils.google_sheets import update_appointment_status, is_connected
        if is_connected():
            await update_appointment_status(apt_id, "cancelled")
    except Exception as _gs_err:
        logger.warning(f"[GSheets] Не вдалося оновити статус: {_gs_err}")

    if user_telegram_id and apt:
        date_formatted = format_date_ru(apt["date"])
        try:
            await bot.send_message(
                user_telegram_id,
                f"ℹ️ <b>Майстер скасував ваш запис</b>\n\n"
                f"💆 Послуга: {apt['service']}\n"
                f"📅 Дата: {date_formatted}\n"
                f"🕐 Час: {apt['time']}\n\n"
                "Зв'яжіться з майстром для уточнення.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не вдалося повідомити клієнта: {e}")
    await callback.answer("✅ Запис видалено")


@router.message(F.text == "📅 Розклад")
async def admin_schedule(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    await state.set_state(AdminStates.choosing_schedule_date)
    await message.answer(
        "📅 <b>Управління розкладом</b>\n\n"
        "Введіть дату у форматі <b>ДД.ММ.РРРР</b>\n"
        "<i>Приклад: 15.01.2025</i>",
        reply_markup=back_kb("admin_back"),
        parse_mode="HTML"
    )


@router.message(AdminStates.choosing_schedule_date)
async def schedule_date_entered(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        date_str = dt.strftime("%Y-%m-%d")
    except ValueError:
        await message.answer(
            "❌ Невірний формат дати. Використовуйте ДД.ММ.РРРР\n"
            "<i>Приклад: 15.01.2025</i>",
            parse_mode="HTML"
        )
        return
    slots = await get_schedule_for_date(date_str)
    date_formatted = format_date_ru(date_str)
    if not slots:
        await message.answer(
            f"📅 <b>{date_formatted}</b>\n\n"
            "Немає слотів на цю дату.\n"
            "Використовуйте <b>➕ Додати слоти</b> для додавання.",
            reply_markup=back_kb("admin_back"),
            parse_mode="HTML"
        )
        return
    await message.answer(
        f"📅 <b>{date_formatted}</b>\n\n"
        "✅ — доступний слот (натисніть щоб закрити)\n"
        "❌ — закритий слот (натисніть щоб відкрити)",
        reply_markup=admin_schedule_kb(date_str, slots),
        parse_mode="HTML"
    )
    await state.clear()


@router.message(F.text == "➕ Додати слоти")
async def admin_add_slots(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.set_state(AdminStates.entering_time_slot)
    await message.answer(
        "➕ <b>Додавання слотів розкладу</b>\n\n"
        "Введіть дату і час у форматі:\n"
        "<code>ДД.ММ.РРРР ГГ:ХХ</code>\n\n"
        "Приклади:\n"
        "<code>15.01.2025 09:00</code>\n"
        "<code>15.01.2025 10:00</code>\n\n"
        "Можна вводити кілька рядків — по одному слоту на рядок.\n"
        "Введіть /cancel для скасування.",
        parse_mode="HTML"
    )


@router.message(AdminStates.entering_time_slot)
async def process_add_slots(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=admin_main_kb())
        return
    lines = message.text.strip().split("\n")
    added = 0
    errors = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split()
            dt = datetime.strptime(parts[0], "%d.%m.%Y")
            t = parts[1]
            datetime.strptime(t, "%H:%M")
            date_str = dt.strftime("%Y-%m-%d")
            await add_schedule_slot(date_str, t)
            added += 1
        except (ValueError, IndexError):
            errors.append(f"❌ Помилка: <code>{line}</code>")
    result = f"✅ Додано слотів: <b>{added}</b>\n"
    if errors:
        result += "\n" + "\n".join(errors)
    await message.answer(result, reply_markup=admin_main_kb(), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("admin_remove_slot:"))
async def admin_toggle_slot_close(callback: CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    parts = callback.data.split(":")
    date_str, time_str = parts[1], parts[2]
    await remove_schedule_slot(date_str, time_str)
    slots = await get_schedule_for_date(date_str)
    date_formatted = format_date_ru(date_str)
    await callback.message.edit_text(
        f"📅 <b>{date_formatted}</b>\n\n"
        f"✅ Слот {time_str} — закрито\n\n"
        "✅ — доступний слот\n❌ — закритий слот",
        reply_markup=admin_schedule_kb(date_str, slots),
        parse_mode="HTML"
    )
    await callback.answer(f"✅ Слот {time_str} закрито")


@router.callback_query(F.data.startswith("admin_open_slot:"))
async def admin_toggle_slot_open(callback: CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    parts = callback.data.split(":")
    date_str, time_str = parts[1], parts[2]
    await add_schedule_slot(date_str, time_str)
    slots = await get_schedule_for_date(date_str)
    date_formatted = format_date_ru(date_str)
    await callback.message.edit_text(
        f"📅 <b>{date_formatted}</b>\n\n"
        f"✅ Слот {time_str} — відкрито\n\n"
        "✅ — доступний слот\n❌ — закритий слот",
        reply_markup=admin_schedule_kb(date_str, slots),
        parse_mode="HTML"
    )
    await callback.answer(f"✅ Слот {time_str} відкрито")


@router.message(F.text == "🗓 Згенерувати тиждень")
async def admin_generate_week(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    await message.answer(
        "🗓 <b>Генерація розкладу на 7 днів</b>\n\n"
        "Буде створено розклад <b>Пн–Пт</b> з <b>09:00 до 17:00</b>\n"
        "(кожну годину) починаючи з сьогодні.\n\n"
        "Підтвердіть дію:",
        reply_markup=admin_generate_week_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_confirm_gen_week")
async def process_generate_week(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫 Немає доступу", show_alert=True)
        return
    work_days = [0, 1, 2, 3, 4]
    time_slots = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
    count = await generate_week_schedule(date.today(), work_days, time_slots)
    await callback.message.edit_text(
        f"✅ <b>Розклад створено!</b>\n"
        f"Додано слотів: <b>{count}</b>\n\n"
        "Використовуйте <b>📅 Розклад</b> для редагування.",
        parse_mode="HTML"
    )
    await callback.message.answer("🧑‍💼 Панель адміністратора:", reply_markup=admin_main_kb())
    await callback.answer("✅ Розклад створено")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🧑‍💼 Повернення до меню.")
    await callback.message.answer("🧑‍💼 Панель адміністратора:", reply_markup=admin_main_kb())
    await callback.answer()


@router.message(Command("seed"))
async def cmd_seed(message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("🚫 Немає доступу.")
        return
    count = await seed_demo_data()
    await message.answer(
        f"✅ <b>Демо-дані завантажено!</b>\n"
        f"Додано слотів розкладу: <b>{count}</b>\n\n"
        "Тепер клієнти можуть записуватись.",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 📅 ТИЖНЕВИЙ ПЕРЕГЛЯД — текстовий огляд у боті
# ─────────────────────────────────────────────────────────────────────────────

DAY_NAMES_FULL = ["Понеділок", "Вівторок", "Середа", "Четвер",
                  "П'ятниця", "Субота", "Неділя"]
MONTH_SHORT = ["", "січ", "лют", "бер", "квіт", "трав", "черв",
               "лип", "серп", "вер", "жовт", "лист", "груд"]


def _week_start(offset_weeks: int = 0) -> date:
    """Повертає понеділок тижня з поточного + offset_weeks тижнів."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(weeks=offset_weeks)


def _format_week_text(week_data: dict) -> list[str]:
    """
    Формує текстовий тижневий огляд.
    - Показує тільки ЗАЙНЯТІ слоти докладно
    - Вільні — тільки підрахунок
    Повертає список частин (по одному дню), щоб не перевищити ліміт 4096 симв.
    """
    all_days = sorted(week_data.keys())
    parts = []

    for day_str in all_days:
        dt = date.fromisoformat(day_str)
        day_label = f"{DAY_NAMES_FULL[dt.weekday()]}, {dt.day} {MONTH_SHORT[dt.month]}"
        slots = week_data[day_str]["slots"]
        if not slots:
            continue

        free_times = []
        booked_lines = []

        for slot in slots:
            t = slot["time"]
            if not slot["is_available"]:
                booked_lines.append(f"  🚫 {t} — <i>закрито майстром</i>")
            elif slot["booked"] and slot["appointment"]:
                apt  = slot["appointment"]
                name = apt.get("name") or "Без імені"
                phone = apt.get("phone") or ""
                svc   = apt.get("service", "")
                if len(svc) > 24:
                    svc = svc[:21] + "…"
                line = f"  🔴 <b>{t}</b> — <b>{name}</b>"
                if phone:
                    line += f" · {phone}"
                line += f"\n       <i>{svc}</i>"
                booked_lines.append(line)
            else:
                free_times.append(t)

        lines = [f"\n📆 <b>{day_label}</b>"]

        if booked_lines:
            lines += booked_lines
        else:
            lines.append("  ✅ <i>Записів немає</i>")

        # Вільні слоти — одним рядком
        if free_times:
            lines.append(
                f"  🟢 Вільно ({len(free_times)}): "
                + ", ".join(free_times)
            )

        parts.append("\n".join(lines))

    return parts


def _week_nav_kb(offset: int):
    """Inline-кнопки навігації між тижнями."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.button(text="◀️ Попередній", callback_data=f"week_view:{offset - 1}")
    builder.button(text="▶️ Наступний", callback_data=f"week_view:{offset + 1}")
    builder.button(text="📅 Цей тиждень", callback_data="week_view:0")
    builder.adjust(2)
    return builder.as_markup()


def _excel_nav_kb(offset: int):
    """Inline-кнопки вибору тижня для Excel."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.button(text="◀️ Попередній", callback_data=f"excel_week:{offset - 1}")
    builder.button(text="▶️ Наступний", callback_data=f"excel_week:{offset + 1}")
    builder.button(text="📅 Цей тиждень", callback_data="excel_week:0")
    builder.adjust(2)
    return builder.as_markup()


async def _send_week_text(target, offset: int):
    """Надсилає текстовий тижневий огляд."""
    start = _week_start(offset)
    end_d = start + timedelta(days=6)
    week_data = await get_week_full_schedule(start, days=7)

    header = (
        f"📅 <b>Тиждень {offset + 1 if offset >= 0 else offset}: "
        f"{start.day} {MONTH_SHORT[start.month]} – "
        f"{end_d.day} {MONTH_SHORT[end_d.month]} {end_d.year}</b>\n"
        f"Майстер: <b>{Config.MASTER_NAME}</b>"
    )

    if not week_data:
        if isinstance(target, CallbackQuery):
            await target.message.answer(
                header + "\n\n😔 Немає слотів у розкладі.",
                reply_markup=_week_nav_kb(offset),
                parse_mode="HTML"
            )
        else:
            await target.answer(
                header + "\n\n😔 Немає слотів у розкладі.",
                reply_markup=_week_nav_kb(offset),
                parse_mode="HTML"
            )
        return

    if isinstance(target, CallbackQuery):
        await target.message.answer(header, parse_mode="HTML")
        msg_target = target.message
    else:
        await target.answer(header, parse_mode="HTML")
        msg_target = target

    day_parts = _format_week_text(week_data)
    for part in day_parts:
        await msg_target.answer(part, parse_mode="HTML")

    await msg_target.answer(
        "📊 Натисніть «📊 Excel» для таблиці або оберіть інший тиждень:",
        reply_markup=_week_nav_kb(offset),
        parse_mode="HTML"
    )


@router.message(F.text == "📅 Тиждень")
async def admin_week_view(message: Message, state: FSMContext):
    """Показати тиждень з записами — НАСТУПНИЙ тиждень якщо сьогодні п'ятниця/субота/неділя."""
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    # Якщо сьогодні чт/пт/сб/нд — автоматично показуємо наступний тиждень
    today = date.today()
    auto_offset = 1 if today.weekday() >= 3 else 0  # чт=3, пт=4, сб=5, нд=6
    await _send_week_text(message, offset=auto_offset)


@router.callback_query(F.data.startswith("week_view:"))
async def admin_week_nav(callback: CallbackQuery):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫", show_alert=True)
        return
    offset = int(callback.data.split(":")[1])
    await callback.answer()
    await _send_week_text(callback, offset=offset)


# ─────────────────────────────────────────────────────────────────────────────
# 📊 EXCEL — генерація і надсилання файлу
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_and_send_excel(bot: Bot, chat_id: int, offset: int,
                                   wait_msg=None):
    """Генерує Excel і відправляє у чат."""
    start = _week_start(offset)
    end_d = start + timedelta(days=6)

    try:
        week_data = await get_week_full_schedule(start, days=7)
        excel_bytes = generate_week_excel(week_data, Config.MASTER_NAME, start)
        filename = (
            f"розклад_{start.strftime('%d%m')}"
            f"-{end_d.strftime('%d%m%Y')}.xlsx"
        )

        booked_total = sum(
            1 for d in week_data.values()
            for s in d["slots"] if s["booked"]
        )
        free_total = sum(
            1 for d in week_data.values()
            for s in d["slots"] if not s["booked"] and s["is_available"]
        )

        await bot.send_document(
            chat_id=chat_id,
            document=BufferedInputFile(excel_bytes, filename=filename),
            caption=(
                f"📊 <b>Розклад на тиждень</b>\n"
                f"{start.day} {MONTH_SHORT[start.month]} – "
                f"{end_d.day} {MONTH_SHORT[end_d.month]} {end_d.year}\n\n"
                f"🔴 Записів: <b>{booked_total}</b>\n"
                f"🟢 Вільних: <b>{free_total}</b>\n\n"
                "Пуста зелена клітинка = вільний слот\n"
                "Клітинка з ім'ям = <b>реальний запис</b>"
            ),
            parse_mode="HTML",
            reply_markup=_excel_nav_kb(offset)
        )
        if wait_msg:
            await wait_msg.delete()

    except Exception as e:
        logger.error(f"Помилка генерації Excel: {e}")
        if wait_msg:
            await wait_msg.edit_text(f"❌ Помилка: {e}")


@router.message(F.text == "📊 Excel")
async def admin_send_excel(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    today = date.today()
    auto_offset = 1 if today.weekday() >= 3 else 0
    wait_msg = await message.answer("⏳ Генерую Excel-таблицю...")
    await _generate_and_send_excel(bot, message.chat.id, auto_offset, wait_msg)
    await message.answer("🧑‍💼 Панель адміністратора:", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("excel_week:"))
async def admin_excel_nav(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("🚫", show_alert=True)
        return
    offset = int(callback.data.split(":")[1])
    await callback.answer("⏳ Генерую...")
    wait_msg = await callback.message.answer("⏳ Генерую Excel-таблицю...")
    await _generate_and_send_excel(bot, callback.message.chat.id, offset, wait_msg)


# ─────────────────────────────────────────────────────────────────────────────
# 🔄 /sync — примусова синхронізація з Google Sheets
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("sync"))
async def cmd_sync(message: Message):
    """Примусово синхронізує всі записи з Google Sheets."""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("🚫 Немає доступу.")
        return

    from utils.google_sheets import is_connected, sync_all_appointments
    from database import get_all_appointments

    if not is_connected():
        await message.answer(
            "⚠️ <b>Google Sheets не підключено.</b>\n\n"
            "Перевірте налаштування <code>GOOGLE_SHEET_ID</code> та <code>GOOGLE_CREDENTIALS</code> у .env файлі.",
            parse_mode="HTML"
        )
        return

    wait = await message.answer("⏳ Синхронізую з Google Sheets...")
    try:
        all_apts = await get_all_appointments(future_only=False)
        count = await sync_all_appointments(all_apts)
        await wait.edit_text(
            f"✅ <b>Синхронізацію завершено!</b>\n"
            f"Записів у таблиці: <b>{count}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Помилка /sync: {e}")
        await wait.edit_text(f"❌ Помилка синхронізації: {e}")
