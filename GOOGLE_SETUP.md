# Налаштування Google Sheets інтеграції

## Що ви отримаєте

Після налаштування бот буде **автоматично** записувати всі бронювання у Google Таблицю в реальному часі:

- ✅ Новий запис → рядок у таблиці (зелений)
- ❌ Скасування → статус оновлюється (червоний)
- 🔄 `/sync` — примусова повна синхронізація

---

## Крок 1: Створити проект у Google Cloud Console

1. Відкрийте [console.cloud.google.com](https://console.cloud.google.com/)
2. Натисніть **"Select a project"** → **"New Project"**
3. Назвіть проект, наприклад: `telegram-booking-bot`
4. Натисніть **"Create"**

---

## Крок 2: Увімкнути Google Sheets API

1. У лівому меню: **APIs & Services** → **Library**
2. Знайдіть **"Google Sheets API"** → натисніть → **"Enable"**
3. Знайдіть **"Google Drive API"** → натисніть → **"Enable"**

---

## Крок 3: Створити Service Account

1. **APIs & Services** → **Credentials** → **"+ Create Credentials"** → **"Service account"**
2. Заповніть:
   - Service account name: `telegram-bot`
   - натисніть **"Create and Continue"**
3. Role: оберіть **"Editor"** → **"Continue"** → **"Done"**
4. Натисніть на щойно створений акаунт у списку
5. Перейдіть на вкладку **"Keys"** → **"Add Key"** → **"Create new key"**
6. Оберіть **JSON** → натисніть **"Create"**
7. Файл `.json` автоматично завантажиться — **збережіть його**!

---

## Крок 4: Додати JSON-ключ до проекту

1. Перейменуйте скачаний файл у `google_credentials.json`
2. Покладіть його у папку з ботом (поруч з `bot.py`)

> ⚠️ **ВАЖЛИВО:** Не завантажуйте цей файл у GitHub/публічні репозиторії!
> Додайте `google_credentials.json` до `.gitignore`

---

## Крок 5: Створити Google Таблицю

1. Відкрийте [sheets.google.com](https://sheets.google.com) → **"+ Blank"**
2. Назвіть таблицю, наприклад: `Записи клієнтів`
3. Скопіюйте **ID таблиці** з URL:
   ```
   https://docs.google.com/spreadsheets/d/  ВОТ_ЦЕЙ_ID  /edit
   ```

---

## Крок 6: Надати доступ Service Account до таблиці

1. Відкрийте файл `google_credentials.json`
2. Знайдіть поле `"client_email"` — скопіюйте адресу (виглядає як `telegram-bot@...iam.gserviceaccount.com`)
3. У Google Таблиці натисніть **"Share"** (Поділитися)
4. Вставте цю email-адресу → роль **"Editor"** → **"Send"**

---

## Крок 7: Налаштувати .env файл

Відкрийте файл `.env` та додайте:

```env
GOOGLE_SHEET_ID=вставте_ID_таблиці_тут
GOOGLE_CREDENTIALS=google_credentials.json
```

---

## Крок 8: Встановити залежності

```bash
pip install gspread google-auth
```

або разом з усіма залежностями:

```bash
pip install -r requirements.txt
```

---

## Перевірка

Запустіть бота. У першому повідомленні майстру побачите:

```
📊 Google Sheets: ✅ підключено, синхронізовано N записів
```

Якщо є помилка — перевірте:
- Файл `google_credentials.json` існує поруч з `bot.py`
- Email сервісного акаунту має доступ до таблиці (крок 6)
- `GOOGLE_SHEET_ID` правильний

---

## Команди для адміна

| Команда | Дія |
|---------|-----|
| `/sync` | Примусова повна синхронізація всіх записів |

---

## Структура таблиці "Записи"

| A: ID | B: Дата | C: Час | D: Послуга | E: Клієнт | F: Телефон | G: Статус | H: Створено | I: Telegram ID |
|-------|---------|--------|-----------|----------|-----------|----------|------------|--------------|

Кольори:
- 🟢 Зелений — підтверджено
- 🔴 Червоний — скасовано
- 🔵 Синій — виконано
