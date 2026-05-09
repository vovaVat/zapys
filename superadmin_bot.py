#!/usr/bin/env python3
"""
superadmin_bot.py — Супер-адмін бот для власника.

Все керування через Telegram — без терміналу:
- Додати нового клієнта (деплой)
- Запустити / зупинити бота клієнта
- Переглянути статистику
- Продовжити ліцензію
- Вимкнути доступ

Запуск: python superadmin_bot.py
"""

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Конфігурація
# ─────────────────────────────────────────────────────────────

SUPERADMIN_TOKEN = os.getenv("SUPERADMIN_BOT_TOKEN", "")
SUPERADMIN_ID    = int(os.getenv("SUPERADMIN_ID", os.getenv("ADMIN_ID", "0")))

BOT_SOURCE_DIR   = Path(__file__).parent.resolve()
BOTS_DIR         = BOT_SOURCE_DIR.parent / "bots"
CLIENTS_JSON     = BOT_SOURCE_DIR / "clients.json"

IS_LINUX = sys.platform.startswith("linux")

EXCLUDE_FILES = {
    ".env", "clients.json", "deploy.py", "superadmin_bot.py",
    "google_credentials.json", "google_credentials.json.json",
    "GOOGLE_SETUP.md", "__pycache__", ".git"
}

if not SUPERADMIN_TOKEN:
    print("❌ Вкажіть SUPERADMIN_BOT_TOKEN у .env файлі")
    exit(1)


# ─────────────────────────────────────────────────────────────
# FSM стани для додавання клієнта
# ─────────────────────────────────────────────────────────────

class AddClientStates(StatesGroup):
    client_id    = State()
    name         = State()
    master_name  = State()
    bot_token    = State()
    admin_id     = State()
    services     = State()
    paid_until   = State()
    confirm      = State()


# ─────────────────────────────────────────────────────────────
# Робота з clients.json
# ─────────────────────────────────────────────────────────────

def load_clients() -> list[dict]:
    if not CLIENTS_JSON.exists():
        return []
    with open(CLIENTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get("clients", [])


def save_clients(clients: list[dict]):
    with open(CLIENTS_JSON, "w", encoding="utf-8") as f:
        json.dump({"clients": clients}, f, ensure_ascii=False, indent=2)


def get_client(client_id: str) -> dict | None:
    return next((c for c in load_clients() if c["id"] == client_id), None)


# ─────────────────────────────────────────────────────────────
# Деплой
# ─────────────────────────────────────────────────────────────

def copy_bot_files(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for item in BOT_SOURCE_DIR.iterdir():
        skip = False
        for pattern in EXCLUDE_FILES:
            if pattern.startswith("*"):
                if item.name.endswith(pattern[1:]):
                    skip = True; break
            elif item.name == pattern:
                skip = True; break
        if skip:
            continue
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, target)


def create_env_file(dest: Path, client: dict):
    services_str = ",".join(client.get("services", ["Манікюр"]))
    paid_line = f"PAID_UNTIL={client.get('paid_until', '')}" if client.get("paid_until") else ""
    content = f"""BOT_TOKEN={client['bot_token']}
ADMIN_ID={client['admin_id']}
MASTER_NAME={client['master_name']}
SERVICES={services_str}
MAX_APPOINTMENTS_PER_DAY=10
REMINDER_HOURS_BEFORE=24
{paid_line}
"""
    with open(dest / ".env", "w", encoding="utf-8") as f:
        f.write(content)


def create_systemd_service(dest: Path, client_id: str) -> str:
    python_path = sys.executable
    service_name = f"tgbot_{client_id}"
    content = f"""[Unit]
Description=Telegram Bot {client_id}
After=network.target

[Service]
Type=simple
WorkingDirectory={dest}
ExecStart={python_path} {dest / 'bot.py'}
Restart=always
RestartSec=10
StandardOutput=append:{dest}/bot.log
StandardError=append:{dest}/bot.log

[Install]
WantedBy=multi-user.target
"""
    service_path = dest / f"{service_name}.service"
    with open(service_path, "w") as f:
        f.write(content)
    return service_name


def deploy_client(client: dict) -> tuple[bool, str]:
    """Деплоїть клієнта. Повертає (успіх, повідомлення)."""
    try:
        dest = Path(client["folder"])
        copy_bot_files(dest)
        create_env_file(dest, client)

        if IS_LINUX:
            service_name = create_systemd_service(dest, client["id"])
            # Копіюємо service файл і запускаємо
            service_src = dest / f"{service_name}.service"
            service_dst = Path(f"/etc/systemd/system/{service_name}.service")
            try:
                subprocess.run(["sudo", "cp", str(service_src), str(service_dst)], check=True)
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
                subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
                subprocess.run(["sudo", "systemctl", "start", service_name], check=True)
                return True, f"✅ Бот запущено через systemd\nСервіс: `{service_name}`"
            except subprocess.CalledProcessError:
                # Якщо немає sudo — запускаємо напряму у фоні
                log_file = open(dest / "bot.log", "a")
                subprocess.Popen(
                    [sys.executable, str(dest / "bot.py")],
                    cwd=str(dest),
                    stdout=log_file,
                    stderr=log_file
                )
                return True, "✅ Бот запущено у фоновому режимі"
        else:
            # Windows — просто запускаємо у фоні
            log_file = open(dest / "bot.log", "a")
            subprocess.Popen(
                [sys.executable, str(dest / "bot.py")],
                cwd=str(dest),
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_LINUX is False else 0
            )
            return True, "✅ Бот запущено"

    except Exception as e:
        return False, f"❌ Помилка деплою: {e}"


def stop_client_bot(client_id: str) -> str:
    """Зупиняє бота клієнта."""
    service_name = f"tgbot_{client_id}"
    if IS_LINUX:
        try:
            subprocess.run(["sudo", "systemctl", "stop", service_name], check=True)
            return "⛔ Бот зупинено"
        except:
            pass
    # Знаходимо процес по шляху і вбиваємо
    try:
        client = get_client(client_id)
        if client:
            bot_path = str(Path(client["folder"]) / "bot.py")
            result = subprocess.run(
                ["pkill" if IS_LINUX else "taskkill", "-f", bot_path],
                capture_output=True
            )
    except:
        pass
    return "⛔ Бот зупинено"


# ─────────────────────────────────────────────────────────────
# Статистика
# ─────────────────────────────────────────────────────────────

def get_client_stats(client: dict) -> dict:
    db_path = Path(client.get("folder", "")) / "bot_database.db"
    stats = {"total": 0, "today": 0, "week": 0, "month": 0,
             "cancelled": 0, "db_exists": db_path.exists()}
    if not db_path.exists():
        return stats
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        today_str = date.today().isoformat()
        month_str = date.today().strftime("%Y-%m")

        cur.execute("SELECT COUNT(*) FROM appointments WHERE status != 'cancelled'")
        stats["total"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM appointments WHERE date = ? AND status != 'cancelled'", (today_str,))
        stats["today"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM appointments WHERE date >= date('now','-7 days') AND status != 'cancelled'")
        stats["week"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM appointments WHERE strftime('%Y-%m',date) = ? AND status != 'cancelled'", (month_str,))
        stats["month"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM appointments WHERE status = 'cancelled'")
        stats["cancelled"] = cur.fetchone()[0]
        conn.close()
    except Exception as e:
        logger.error(f"БД {client['id']}: {e}")
    return stats


def check_license(client: dict) -> tuple[bool, str]:
    if not client.get("active", True):
        return False, "❌ Вимкнено"
    paid_until = client.get("paid_until", "")
    if not paid_until:
        return True, "✅ Безстроковий"
    try:
        expiry = date.fromisoformat(paid_until)
        delta = (expiry - date.today()).days
        if delta < 0:
            return False, f"⏰ Прострочено ({abs(delta)} дн. тому)"
        elif delta <= 7:
            return True, f"⚠️ Закінчується через {delta} дн."
        else:
            return True, f"✅ До {expiry.strftime('%d.%m.%Y')}"
    except ValueError:
        return True, "✅ Активний"


# ─────────────────────────────────────────────────────────────
# Клавіатури
# ─────────────────────────────────────────────────────────────

def main_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Додати клієнта",      callback_data="sa_add")
    b.button(text="📋 Всі клієнти",         callback_data="sa_list")
    b.button(text="📊 Зведена статистика",  callback_data="sa_total_stats")
    b.button(text="⏰ Закінчується оплата", callback_data="sa_expiring")
    b.adjust(1)
    return b.as_markup()


def clients_list_kb(clients: list[dict]):
    b = InlineKeyboardBuilder()
    for c in clients:
        active, _ = check_license(c)
        icon = "🟢" if active else "🔴"
        b.button(text=f"{icon} {c['name']}", callback_data=f"sa_client:{c['id']}")
    b.button(text="◀️ Меню", callback_data="sa_menu")
    b.adjust(1)
    return b.as_markup()


def client_kb(client_id: str, active: bool):
    b = InlineKeyboardBuilder()
    b.button(text="▶️ Запустити бота",      callback_data=f"sa_start:{client_id}")
    b.button(text="⛔ Зупинити бота",       callback_data=f"sa_stop:{client_id}")
    if active:
        b.button(text="🔒 Вимкнути доступ", callback_data=f"sa_disable:{client_id}")
    else:
        b.button(text="🔓 Увімкнути доступ",callback_data=f"sa_enable:{client_id}")
    b.button(text="📅 Продовжити +30 дн.",  callback_data=f"sa_extend:{client_id}")
    b.button(text="◀️ Назад",              callback_data="sa_list")
    b.adjust(2, 1, 1, 1)
    return b.as_markup()


def cancel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="❌ Скасувати", callback_data="sa_cancel_add")
    return b.as_markup()


# ─────────────────────────────────────────────────────────────
# Роутер
# ─────────────────────────────────────────────────────────────

router = Router()

def guard(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID


# ─── /start ───────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not guard(message.from_user.id):
        await message.answer("🚫 Немає доступу.")
        return
    await state.clear()
    clients = load_clients()
    active_count = sum(1 for c in clients if check_license(c)[0])
    await message.answer(
        "👑 <b>Супер-адмін панель</b>\n\n"
        f"Клієнтів: <b>{len(clients)}</b>  |  Активних: <b>{active_count}</b>\n\n"
        "Оберіть дію:",
        reply_markup=main_menu_kb()
    )


@router.callback_query(F.data == "sa_menu")
async def sa_menu(callback: CallbackQuery, state: FSMContext):
    if not guard(callback.from_user.id): return
    await state.clear()
    clients = load_clients()
    active_count = sum(1 for c in clients if check_license(c)[0])
    await callback.message.edit_text(
        "👑 <b>Супер-адмін панель</b>\n\n"
        f"Клієнтів: <b>{len(clients)}</b>  |  Активних: <b>{active_count}</b>\n\n"
        "Оберіть дію:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


# ─── Список клієнтів ──────────────────────────────────────────

@router.callback_query(F.data == "sa_list")
async def sa_list(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    clients = load_clients()
    if not clients:
        await callback.message.edit_text(
            "📋 Клієнтів ще немає.\n\nНатисніть ➕ щоб додати першого.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    text = "📋 <b>Всі клієнти:</b>\n\n"
    for c in clients:
        active, lic = check_license(c)
        stats = get_client_stats(c)
        text += f"{'🟢' if active else '🔴'} <b>{c['name']}</b> · {lic}\n"
        text += f"   Записів сьогодні: {stats['today']} | місяць: {stats['month']}\n\n"

    await callback.message.edit_text(text, reply_markup=clients_list_kb(clients))
    await callback.answer()


# ─── Картка клієнта ───────────────────────────────────────────

@router.callback_query(F.data.startswith("sa_client:"))
async def sa_client(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    client = get_client(client_id)
    if not client:
        await callback.answer("❌ Не знайдено", show_alert=True)
        return

    active, lic = check_license(client)
    stats = get_client_stats(client)

    text = (
        f"👤 <b>{client['name']}</b>\n"
        f"Майстер: {client['master_name']}\n"
        f"ID: <code>{client_id}</code>\n"
        f"З: {client.get('created_at', '—')}\n\n"
        f"🔑 Ліцензія: {lic}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"Сьогодні: <b>{stats['today']}</b>\n"
        f"Тиждень: <b>{stats['week']}</b>\n"
        f"Місяць: <b>{stats['month']}</b>\n"
        f"Всього: <b>{stats['total']}</b>\n"
        f"Скасовано: <b>{stats['cancelled']}</b>"
    )
    if not stats["db_exists"]:
        text += "\n\n⚠️ <i>БД не знайдена — бот ще не запускався</i>"

    await callback.message.edit_text(text, reply_markup=client_kb(client_id, active))
    await callback.answer()


# ─── Запуск / зупинка ─────────────────────────────────────────

@router.callback_query(F.data.startswith("sa_start:"))
async def sa_start(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    client = get_client(client_id)
    if not client:
        await callback.answer("❌ Не знайдено", show_alert=True)
        return
    await callback.answer("⏳ Запускаю...")
    msg = await callback.message.answer("⏳ Запускаю бота...")
    ok, result = deploy_client(client)
    await msg.edit_text(f"{'✅' if ok else '❌'} {result}")


@router.callback_query(F.data.startswith("sa_stop:"))
async def sa_stop(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Зупиняю...")
    result = stop_client_bot(client_id)
    await callback.message.answer(result)


# ─── Вимкнути / увімкнути доступ ─────────────────────────────

@router.callback_query(F.data.startswith("sa_disable:"))
async def sa_disable(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    clients = load_clients()
    for c in clients:
        if c["id"] == client_id:
            c["active"] = False
            break
    save_clients(clients)
    stop_client_bot(client_id)
    await callback.answer("🔒 Доступ вимкнено", show_alert=True)
    callback.data = f"sa_client:{client_id}"
    await sa_client(callback)


@router.callback_query(F.data.startswith("sa_enable:"))
async def sa_enable(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    clients = load_clients()
    for c in clients:
        if c["id"] == client_id:
            c["active"] = True
            break
    save_clients(clients)
    await callback.answer("🔓 Доступ увімкнено", show_alert=True)
    callback.data = f"sa_client:{client_id}"
    await sa_client(callback)


# ─── Продовжити ліцензію ──────────────────────────────────────

@router.callback_query(F.data.startswith("sa_extend:"))
async def sa_extend(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    client_id = callback.data.split(":", 1)[1]
    clients = load_clients()
    new_date = None
    for c in clients:
        if c["id"] == client_id:
            paid = c.get("paid_until", "")
            try:
                base = max(date.fromisoformat(paid), date.today()) if paid else date.today()
            except ValueError:
                base = date.today()
            new_date = base + timedelta(days=30)
            c["paid_until"] = new_date.isoformat()
            c["active"] = True
            break
    save_clients(clients)
    await callback.answer(f"✅ До {new_date.strftime('%d.%m.%Y')}", show_alert=True)
    callback.data = f"sa_client:{client_id}"
    await sa_client(callback)


# ─── Зведена статистика ───────────────────────────────────────

@router.callback_query(F.data == "sa_total_stats")
async def sa_total_stats(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    clients = load_clients()
    if not clients:
        await callback.answer("Клієнтів немає", show_alert=True)
        return

    total_today = total_week = total_month = total_all = 0
    text = "📊 <b>Статистика по всіх клієнтах:</b>\n\n"
    for c in clients:
        s = get_client_stats(c)
        total_today += s["today"]; total_week += s["week"]
        total_month += s["month"]; total_all  += s["total"]
        active, _ = check_license(c)
        text += f"{'🟢' if active else '🔴'} <b>{c['name']}</b>: сьогодні {s['today']} | міс. {s['month']} | всього {s['total']}\n"

    text += f"\n<b>РАЗОМ:</b> сьогодні {total_today} | тиждень {total_week} | місяць {total_month} | всього {total_all}"
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Меню", callback_data="sa_menu")
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


# ─── Закінчується оплата ──────────────────────────────────────

@router.callback_query(F.data == "sa_expiring")
async def sa_expiring(callback: CallbackQuery):
    if not guard(callback.from_user.id): return
    clients = load_clients()
    expiring = []
    for c in clients:
        paid = c.get("paid_until", "")
        if not paid: continue
        try:
            expiry = date.fromisoformat(paid)
            delta = (expiry - date.today()).days
            if delta <= 14:
                expiring.append((c, delta, expiry))
        except ValueError:
            pass

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Меню", callback_data="sa_menu")

    if not expiring:
        await callback.message.edit_text("✅ Жодна оплата не закінчується найближчі 14 днів", reply_markup=b.as_markup())
        await callback.answer()
        return

    text = "⏰ <b>Закінчується оплата:</b>\n\n"
    for c, delta, expiry in sorted(expiring, key=lambda x: x[1]):
        if delta < 0:
            status = f"‼️ Прострочено {abs(delta)} дн. тому"
        elif delta == 0:
            status = "‼️ Сьогодні!"
        else:
            status = f"⚠️ Через {delta} дн. ({expiry.strftime('%d.%m')})"
        text += f"• <b>{c['name']}</b> — {status}\n"

    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# ➕ ДОДАВАННЯ НОВОГО КЛІЄНТА через FSM
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "sa_add")
async def sa_add_start(callback: CallbackQuery, state: FSMContext):
    if not guard(callback.from_user.id): return
    await state.set_state(AddClientStates.client_id)
    await callback.message.edit_text(
        "➕ <b>Додавання нового клієнта</b>\n\n"
        "Крок 1/7\n"
        "Введіть <b>ID клієнта</b> — латиниця без пробілів\n"
        "<i>Приклад: salon_anna, master_olga</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "sa_cancel_add")
async def sa_cancel_add(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Скасовано", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(AddClientStates.client_id)
async def add_client_id(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    client_id = message.text.strip().lower().replace(" ", "_")

    if get_client(client_id):
        await message.answer(f"❌ Клієнт '{client_id}' вже існує. Введіть інший ID:", reply_markup=cancel_kb())
        return

    await state.update_data(client_id=client_id)
    await state.set_state(AddClientStates.name)
    await message.answer(
        f"✅ ID: <code>{client_id}</code>\n\n"
        "Крок 2/7\n"
        "Введіть <b>назву бізнесу</b>:\n"
        "<i>Приклад: Салон Анна, Студія краси</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.name)
async def add_client_name(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddClientStates.master_name)
    await message.answer(
        "Крок 3/7\n"
        "Введіть <b>ім'я майстра</b> (відображається в боті):\n"
        "<i>Приклад: Анна, Єгор - Майстер</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.master_name)
async def add_client_master(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    await state.update_data(master_name=message.text.strip())
    await state.set_state(AddClientStates.bot_token)
    await message.answer(
        "Крок 4/7\n"
        "Введіть <b>токен бота</b> (від @BotFather):\n"
        "<i>Виглядає так: 1234567890:AABBcc...</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.bot_token)
async def add_client_token(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    token = message.text.strip()
    if ":" not in token or len(token) < 30:
        await message.answer("❌ Схоже це не токен. Спробуйте ще раз:", reply_markup=cancel_kb())
        return
    await state.update_data(bot_token=token)
    await state.set_state(AddClientStates.admin_id)
    await message.answer(
        "Крок 5/7\n"
        "Введіть <b>Telegram ID адміна</b> (клієнт дізнається у @userinfobot):\n"
        "<i>Приклад: 384729183</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.admin_id)
async def add_client_admin(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID має бути числом. Спробуйте ще раз:", reply_markup=cancel_kb())
        return
    await state.update_data(admin_id=admin_id)
    await state.set_state(AddClientStates.services)
    await message.answer(
        "Крок 6/7\n"
        "Введіть <b>послуги через кому</b>:\n"
        "<i>Приклад: Манікюр, Педикюр, Нарощування\n"
        "Або натисніть Enter щоб використати стандартні</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.services)
async def add_client_services(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    text = message.text.strip()
    services = [s.strip() for s in text.split(",")] if text else ["Манікюр", "Педикюр", "Нарощування"]
    await state.update_data(services=services)
    await state.set_state(AddClientStates.paid_until)
    await message.answer(
        "Крок 7/7\n"
        "Оплачено до якої дати? Введіть у форматі <b>РРРР-ММ-ДД</b>\n"
        "<i>Або напишіть 0 якщо безстроково</i>",
        reply_markup=cancel_kb()
    )


@router.message(AddClientStates.paid_until)
async def add_client_paid(message: Message, state: FSMContext):
    if not guard(message.from_user.id): return
    text = message.text.strip()
    paid_until = ""
    if text != "0":
        try:
            date.fromisoformat(text)
            paid_until = text
        except ValueError:
            await message.answer(
                "❌ Невірний формат. Введіть РРРР-ММ-ДД або 0:",
                reply_markup=cancel_kb()
            )
            return

    await state.update_data(paid_until=paid_until)
    data = await state.get_data()
    await state.set_state(AddClientStates.confirm)

    lic_text = f"До {paid_until}" if paid_until else "Безстроково"
    summary = (
        "📋 <b>Перевірте дані:</b>\n\n"
        f"ID: <code>{data['client_id']}</code>\n"
        f"Назва: {data['name']}\n"
        f"Майстер: {data['master_name']}\n"
        f"Послуги: {', '.join(data['services'])}\n"
        f"Ліцензія: {lic_text}\n\n"
        "Все вірно?"
    )
    b = InlineKeyboardBuilder()
    b.button(text="✅ Деплоїти!", callback_data="sa_confirm_deploy")
    b.button(text="❌ Скасувати", callback_data="sa_cancel_add")
    b.adjust(1)
    await message.answer(summary, reply_markup=b.as_markup())


@router.callback_query(F.data == "sa_confirm_deploy")
async def sa_confirm_deploy(callback: CallbackQuery, state: FSMContext):
    if not guard(callback.from_user.id): return
    data = await state.get_data()
    await state.clear()

    client_id = data["client_id"]
    dest = BOTS_DIR / client_id
    client = {
        "id": client_id,
        "name": data["name"],
        "master_name": data["master_name"],
        "bot_token": data["bot_token"],
        "admin_id": data["admin_id"],
        "services": data["services"],
        "folder": str(dest),
        "created_at": date.today().isoformat(),
        "paid_until": data.get("paid_until", ""),
        "active": True
    }

    await callback.message.edit_text("⏳ Деплою бота...")
    ok, result = deploy_client(client)

    if ok:
        clients = load_clients()
        clients.append(client)
        save_clients(clients)
        await callback.message.edit_text(
            f"🎉 <b>Клієнт '{data['name']}' успішно додано!</b>\n\n"
            f"{result}\n\n"
            f"Папка: <code>{dest}</code>",
            reply_markup=main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Помилка деплою:</b>\n{result}",
            reply_markup=main_menu_kb()
        )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# Запуск
# ─────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=SUPERADMIN_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("👑 Супер-адмін бот запущено")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
