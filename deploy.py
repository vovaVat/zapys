#!/usr/bin/env python3
"""
deploy.py — Скрипт автоматичного деплою нового клієнта.

Використання:
    python deploy.py                    # інтерактивний режим
    python deploy.py --list             # список всіх клієнтів
    python deploy.py --disable client01 # вимкнути клієнта
    python deploy.py --enable  client01 # увімкнути клієнта
    python deploy.py --remove  client01 # видалити клієнта
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from datetime import datetime, date
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Налаштування
# ─────────────────────────────────────────────────────────────

# Папка звідки беруться вихідні файли бота (ця папка)
BOT_SOURCE_DIR = Path(__file__).parent.resolve()

# Куди кладемо окремі екземпляри клієнтів
# На сервері: /home/user/bots/   На Windows: поруч з цим скриптом у bots/
BOTS_DIR = BOT_SOURCE_DIR.parent / "bots"

# Файл зі списком клієнтів
CLIENTS_JSON = BOT_SOURCE_DIR / "clients.json"

# Файли які НЕ копіюємо в нову папку клієнта
EXCLUDE_FILES = {
    ".env", "clients.json", "deploy.py", "superadmin_bot.py",
    "*.db", "*.sqlite", "__pycache__", ".git",
    "google_credentials.json", "google_credentials.json.json",
    "GOOGLE_SETUP.md"
}


# ─────────────────────────────────────────────────────────────
# Робота з clients.json
# ─────────────────────────────────────────────────────────────

def load_clients() -> dict:
    if CLIENTS_JSON.exists():
        with open(CLIENTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"clients": []}


def save_clients(data: dict):
    with open(CLIENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_client(client_id: str) -> dict | None:
    data = load_clients()
    for c in data["clients"]:
        if c["id"] == client_id:
            return c
    return None


# ─────────────────────────────────────────────────────────────
# Копіювання файлів бота
# ─────────────────────────────────────────────────────────────

def copy_bot_files(dest: Path):
    """Копіює всі файли бота (крім виключених) у папку клієнта."""
    dest.mkdir(parents=True, exist_ok=True)

    for item in BOT_SOURCE_DIR.iterdir():
        # Пропускаємо виключені файли та папки
        skip = False
        for pattern in EXCLUDE_FILES:
            if pattern.startswith("*"):
                if item.name.endswith(pattern[1:]):
                    skip = True
                    break
            elif item.name == pattern:
                skip = True
                break
        if skip:
            continue

        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, target)

    print(f"  ✅ Файли скопійовано → {dest}")


# ─────────────────────────────────────────────────────────────
# Створення .env
# ─────────────────────────────────────────────────────────────

def create_env(dest: Path, client: dict):
    """Генерує .env файл для клієнта."""
    services_str = ",".join(client.get("services", ["Манікюр", "Педикюр"]))

    paid_until = client.get("paid_until", "")
    license_line = f"\n# Ліцензія\nPAID_UNTIL={paid_until}" if paid_until else ""

    env_content = f"""# ═══════════════════════════════════════════
# Telegram Bot — {client['master_name']}
# Клієнт: {client['name']}
# Деплой: {datetime.now().strftime('%Y-%m-%d %H:%M')}
# ═══════════════════════════════════════════

BOT_TOKEN={client['bot_token']}
ADMIN_ID={client['admin_id']}
MASTER_NAME={client['master_name']}
SERVICES={services_str}

MAX_APPOINTMENTS_PER_DAY=10
REMINDER_HOURS_BEFORE=24
{license_line}
"""
    env_path = dest / ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    print(f"  ✅ .env створено")


# ─────────────────────────────────────────────────────────────
# systemd сервіс (для Linux)
# ─────────────────────────────────────────────────────────────

def create_systemd_service(dest: Path, client_id: str) -> str:
    """Генерує .service файл для systemd."""
    python_path = sys.executable
    service_name = f"tgbot_{client_id}"
    service_content = f"""[Unit]
Description=Telegram Bot — {client_id}
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
    service_file = dest / f"{service_name}.service"
    with open(service_file, "w") as f:
        f.write(service_content)

    return service_name


# ─────────────────────────────────────────────────────────────
# Інтерактивний деплой нового клієнта
# ─────────────────────────────────────────────────────────────

def deploy_new_client():
    print("\n" + "═" * 50)
    print("  🚀 ДЕПЛОЙ НОВОГО КЛІЄНТА")
    print("═" * 50)

    data = load_clients()

    # Збір інформації
    print("\n📋 Введіть дані клієнта:\n")

    client_id = input("  ID клієнта (латиниця, без пробілів, напр. salon_anna): ").strip()
    if not client_id:
        print("❌ ID не може бути пустим")
        return

    if get_client(client_id):
        print(f"❌ Клієнт '{client_id}' вже існує")
        return

    name = input("  Назва бізнесу (напр. Салон Анна): ").strip()
    master_name = input("  Ім'я майстра (відображається в боті): ").strip()
    bot_token = input("  Bot Token (від @BotFather): ").strip()
    admin_id = input("  Telegram ID адміна (від @userinfobot): ").strip()

    services_input = input(
        "  Послуги через кому (Enter = Манікюр,Педикюр,Нарощування): "
    ).strip()
    services = [s.strip() for s in services_input.split(",")] if services_input else [
        "Манікюр", "Педикюр", "Нарощування нігтів"
    ]

    paid_until = input("  Оплачено до (РРРР-ММ-ДД, Enter = без обмежень): ").strip()

    # Підтвердження
    print("\n" + "─" * 40)
    print(f"  ID:         {client_id}")
    print(f"  Назва:      {name}")
    print(f"  Майстер:    {master_name}")
    print(f"  Admin ID:   {admin_id}")
    print(f"  Послуги:    {', '.join(services)}")
    if paid_until:
        print(f"  Оплата до:  {paid_until}")
    print("─" * 40)

    confirm = input("\nПідтвердити деплой? (y/n): ").strip().lower()
    if confirm != "y":
        print("❌ Скасовано")
        return

    # Деплой
    print("\n⏳ Деплой...\n")

    dest = BOTS_DIR / client_id
    client = {
        "id": client_id,
        "name": name,
        "master_name": master_name,
        "bot_token": bot_token,
        "admin_id": int(admin_id),
        "services": services,
        "folder": str(dest),
        "created_at": date.today().isoformat(),
        "paid_until": paid_until,
        "active": True
    }

    copy_bot_files(dest)
    create_env(dest, client)

    is_linux = sys.platform.startswith("linux")
    if is_linux:
        service_name = create_systemd_service(dest, client_id)
        print(f"  ✅ systemd сервіс: {service_name}.service")
        print(f"\n  📌 Щоб запустити на сервері:")
        print(f"     sudo cp {dest}/{service_name}.service /etc/systemd/system/")
        print(f"     sudo systemctl daemon-reload")
        print(f"     sudo systemctl enable {service_name}")
        print(f"     sudo systemctl start {service_name}")
    else:
        print(f"\n  📌 Щоб запустити бота:")
        print(f"     cd {dest}")
        print(f"     python bot.py")

    # Зберігаємо в clients.json
    data["clients"].append(client)
    save_clients(data)

    print(f"\n✅ Клієнт '{client_id}' успішно задеплоєно!")
    print(f"   Папка: {dest}")


# ─────────────────────────────────────────────────────────────
# Управління клієнтами
# ─────────────────────────────────────────────────────────────

def list_clients():
    data = load_clients()
    if not data["clients"]:
        print("📋 Клієнтів немає")
        return

    print("\n" + "═" * 60)
    print(f"  {'ID':<20} {'Назва':<20} {'Статус':<10} {'Оплата до'}")
    print("═" * 60)

    for c in data["clients"]:
        status = "✅ Активний" if c.get("active") else "❌ Вимкнений"
        paid = c.get("paid_until", "∞") or "∞"

        # Перевірка чи не прострочена оплата
        if c.get("paid_until"):
            try:
                if date.fromisoformat(c["paid_until"]) < date.today():
                    status = "⏰ Прострочено"
            except ValueError:
                pass

        print(f"  {c['id']:<20} {c['name']:<20} {status:<12} {paid}")

    print("═" * 60)
    print(f"  Всього: {len(data['clients'])} клієнтів\n")


def set_client_active(client_id: str, active: bool):
    data = load_clients()
    for c in data["clients"]:
        if c["id"] == client_id:
            c["active"] = active
            save_clients(data)
            status = "активовано ✅" if active else "вимкнено ❌"
            print(f"✅ Клієнт '{client_id}' {status}")
            return
    print(f"❌ Клієнта '{client_id}' не знайдено")


def remove_client(client_id: str):
    data = load_clients()
    client = get_client(client_id)
    if not client:
        print(f"❌ Клієнта '{client_id}' не знайдено")
        return

    confirm = input(f"⚠️  Видалити клієнта '{client_id}' та всі його файли? (y/n): ")
    if confirm.lower() != "y":
        print("Скасовано")
        return

    folder = Path(client.get("folder", ""))
    if folder.exists():
        shutil.rmtree(folder)
        print(f"  ✅ Папка видалена: {folder}")

    data["clients"] = [c for c in data["clients"] if c["id"] != client_id]
    save_clients(data)
    print(f"✅ Клієнт '{client_id}' видалений")


# ─────────────────────────────────────────────────────────────
# Головна функція
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Telegram Bot — Деплой клієнтів")
    parser.add_argument("--list",    action="store_true", help="Список клієнтів")
    parser.add_argument("--disable", metavar="ID",        help="Вимкнути клієнта")
    parser.add_argument("--enable",  metavar="ID",        help="Увімкнути клієнта")
    parser.add_argument("--remove",  metavar="ID",        help="Видалити клієнта")
    args = parser.parse_args()

    if args.list:
        list_clients()
    elif args.disable:
        set_client_active(args.disable, False)
    elif args.enable:
        set_client_active(args.enable, True)
    elif args.remove:
        remove_client(args.remove)
    else:
        deploy_new_client()


if __name__ == "__main__":
    main()
