"""
handlers/start.py — Обробник команди /start та головного меню.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from config import Config
from database import get_or_create_user
from keyboards import main_menu_kb, admin_main_kb

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await get_or_create_user(message.from_user.id)
    is_admin = message.from_user.id == Config.ADMIN_ID
    if is_admin:
        greeting = (
            f"👋 Вітаємо, <b>{message.from_user.first_name}</b>!\n\n"
            f"🔑 Ви увійшли як <b>адміністратор</b>\n\n"
            "Оберіть дію в меню нижче 👇"
        )
        kb = admin_main_kb()
    else:
        greeting = (
            f"👋 Вітаємо, <b>{message.from_user.first_name}</b>!\n\n"
            f"💅 Ласкаво просимо до майстра <b>{Config.MASTER_NAME}</b>\n\n"
            "Тут ви можете:\n"
            "📅 Записатись на послугу\n"
            "📋 Переглянути свої записи\n"
            "❌ Скасувати запис\n\n"
            "Оберіть дію в меню нижче 👇"
        )
        kb = main_menu_kb()
    await message.answer(greeting, reply_markup=kb, parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == Config.ADMIN_ID
    kb = admin_main_kb() if is_admin else main_menu_kb()
    await message.answer("🏠 Головне меню", reply_markup=kb)


@router.message(F.text == "ℹ️ Про майстра")
async def about_master(message: Message):
    text = (
        f"✨ <b>{Config.MASTER_NAME}</b>\n\n"
        "🎓 Професійний майстер з багаторічним досвідом роботи\n\n"
        "<b>Послуги:</b>\n"
    )
    for service, duration in Config.SERVICES.items():
        text += f"• {service} — {duration} хв\n"
    text += "\n📍 Адреса: уточнюйте при записі"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📞 Контакти")
async def contacts(message: Message):
    text = (
        "📞 <b>Контакти</b>\n\n"
        f"👤 Майстер: {Config.MASTER_NAME}\n"
        "📱 Телефон: уточніть у майстра\n"
        "💬 Telegram: напишіть нам прямо тут!\n\n"
        "⏰ <b>Режим роботи:</b>\n"
        "Пн–Пт: 9:00 – 18:00\n"
        "Сб: за записом\n"
        "Нд: вихідний"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "👤 Режим клієнта")
async def switch_to_client(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID:
        return
    await state.clear()
    await message.answer(
        "👤 Режим клієнта активовано.\nКоманда /start щоб повернутись до адмін-меню.",
        reply_markup=main_menu_kb()
    )
