"""
utils/excel_export.py — Генерація Excel-звіту тижневого розкладу.

Логіка відображення:
  - Зайнятий слот (є запис) → 🔴 червона клітинка + ім'я / телефон / послуга
  - Вільний слот            → пуста зелена клітинка (БЕЗ ТЕКСТУ — не плутати з записом)
  - Закритий слот           → сіра клітинка «Закрито»
  - Відсутній слот          → клітинка «—»
"""

import io
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─── Кольори ───────────────────────────────────────────────────────────────
COLOR_FREE        = "E2EFDA"   # ніжно-зелений фон — вільно (БЕЗ тексту)
COLOR_BOOKED_BG   = "FFC7CE"   # рожево-червоний — зайнято
COLOR_BOOKED_FONT = "9C0006"   # темно-червоний текст
COLOR_CLOSED_BG   = "D9D9D9"   # сірий — слот закрито
COLOR_CLOSED_FONT = "595959"
COLOR_EMPTY       = "F7F7F7"   # майже білий — слот не існує
COLOR_HEADER_BG   = "1F497D"   # темно-синій — шапка дня
COLOR_TIME_BG     = "4472C4"   # синій — стовпець часу
COLOR_TITLE_BG    = "1F3864"   # заголовок звіту

DAY_NAMES_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTH_NAMES_UA = [
    "", "січ", "лют", "бер", "квіт", "трав", "черв",
    "лип", "серп", "вер", "жовт", "лист", "груд"
]


def _border():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)


def _set(ws, row, col, value, bg, font_color="000000", bold=False,
         size=10, h_align="center", wrap=False):
    c = ws.cell(row=row, column=col, value=value)
    c.fill = PatternFill("solid", start_color=bg)
    c.font = Font(name="Arial", size=size, bold=bold, color=font_color)
    c.alignment = Alignment(horizontal=h_align, vertical="center", wrap_text=wrap)
    c.border = _border()
    return c


def generate_week_excel(week_data: dict, master_name: str, start_date: date) -> bytes:
    """
    Генерує Excel-файл тижневого розкладу.

    Вільні слоти — зелений фон, ПОРОЖНЯ клітинка.
    Зайняті слоти — червоний фон, ім'я / телефон / послуга.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Розклад"

    # Всі унікальні часи і дні (відсортовано)
    all_times = sorted({
        s["time"]
        for d in week_data.values()
        for s in d["slots"]
    })
    all_days = sorted(week_data.keys())

    if not all_days or not all_times:
        ws["A1"] = "Немає даних для відображення"
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    end_date = date.fromisoformat(all_days[-1])

    # ─── Рядок 1: заголовок ────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=1 + len(all_days))
    title = (
        f"{master_name}   |   Розклад  "
        f"{start_date.day} {MONTH_NAMES_UA[start_date.month]} – "
        f"{end_date.day} {MONTH_NAMES_UA[end_date.month]} {end_date.year}"
    )
    tc = ws.cell(row=1, column=1, value=title)
    tc.fill  = PatternFill("solid", start_color=COLOR_TITLE_BG)
    tc.font  = Font(name="Arial", size=13, bold=True, color="FFFFFF")
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # ─── Рядок 2: шапка (час + дні) ───────────────────────────────────────
    _set(ws, 2, 1, "Час", COLOR_TIME_BG, "FFFFFF", bold=True, size=11)
    ws.row_dimensions[2].height = 40

    for ci, day_str in enumerate(all_days, start=2):
        dt = date.fromisoformat(day_str)
        label = f"{DAY_NAMES_UA[dt.weekday()]}\n{dt.day} {MONTH_NAMES_UA[dt.month]}"
        c = _set(ws, 2, ci, label, COLOR_HEADER_BG, "FFFFFF",
                 bold=True, size=11, wrap=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # ─── Рядки даних ───────────────────────────────────────────────────────
    for ri, time_str in enumerate(all_times, start=3):
        ws.row_dimensions[ri].height = 52
        _set(ws, ri, 1, time_str, COLOR_TIME_BG, "FFFFFF", bold=True, size=11)

        for ci, day_str in enumerate(all_days, start=2):
            slots = week_data.get(day_str, {}).get("slots", [])
            slot  = next((s for s in slots if s["time"] == time_str), None)

            if slot is None:
                # Цього слоту немає в розкладі цього дня
                _set(ws, ri, ci, "—", COLOR_EMPTY, "AAAAAA", size=9)

            elif not slot["is_available"]:
                # Майстер закрив слот
                _set(ws, ri, ci, "🚫 Закрито", COLOR_CLOSED_BG, COLOR_CLOSED_FONT, size=9)

            elif slot["booked"] and slot["appointment"]:
                # ── ЗАЙНЯТИЙ СЛОТ ──────────────────────────────────────
                apt  = slot["appointment"]
                name = apt.get("name") or "—"
                phone = apt.get("phone") or ""
                svc   = apt.get("service", "")
                if len(svc) > 24:
                    svc = svc[:21] + "…"
                text = f"{name}"
                if phone:
                    text += f"\n{phone}"
                if svc:
                    text += f"\n{svc}"
                c = ws.cell(row=ri, column=ci, value=text)
                c.fill      = PatternFill("solid", start_color=COLOR_BOOKED_BG)
                c.font      = Font(name="Arial", size=9, bold=True,
                                   color=COLOR_BOOKED_FONT)
                c.alignment = Alignment(horizontal="left", vertical="center",
                                        wrap_text=True)
                c.border    = _border()

            else:
                # ── ВІЛЬНИЙ СЛОТ — ПОРОЖНЯ КЛІТИНКА (зелений фон) ──────
                # Навмисно БЕЗ тексту, щоб не плутати з записом
                _set(ws, ri, ci, "", COLOR_FREE)

    # ─── Легенда ───────────────────────────────────────────────────────────
    lr = len(all_times) + 4
    ws.merge_cells(start_row=lr - 1, start_column=1,
                   end_row=lr - 1, end_column=4)
    lh = ws.cell(row=lr - 1, column=1, value="Легенда:")
    lh.font = Font(name="Arial", size=10, bold=True)
    lh.alignment = Alignment(horizontal="left")
    ws.row_dimensions[lr - 1].height = 18

    legend = [
        ("(порожньо) — вільний слот", COLOR_FREE,      "276221"),
        ("Ім'я / тел. — ЗАПИС",       COLOR_BOOKED_BG, COLOR_BOOKED_FONT),
        ("🚫 Закрито",                 COLOR_CLOSED_BG, COLOR_CLOSED_FONT),
    ]
    ws.row_dimensions[lr].height = 20
    for i, (lbl, bg, fg) in enumerate(legend, start=1):
        _set(ws, lr, i, lbl, bg, fg, size=9)

    # ─── Ширини стовпців ───────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 8
    for ci in range(2, 2 + len(all_days)):
        ws.column_dimensions[get_column_letter(ci)].width = 20

    ws.freeze_panes = "B3"

    # ─── Аркуш 2: список записів ───────────────────────────────────────────
    ws2 = wb.create_sheet("Записи")
    headers = ["#", "Дата", "День", "Час", "Послуга", "Клієнт", "Телефон"]
    for ci, h in enumerate(headers, start=1):
        _set(ws2, 1, ci, h, COLOR_HEADER_BG, "FFFFFF", bold=True, size=11)
    ws2.row_dimensions[1].height = 28

    widths = [4, 12, 8, 8, 32, 20, 16]
    for ci, w in enumerate(widths, start=1):
        ws2.column_dimensions[get_column_letter(ci)].width = w
    ws2.freeze_panes = "A2"

    num = 1
    for day_str in all_days:
        dt   = date.fromisoformat(day_str)
        dlbl = f"{dt.day:02d}.{dt.month:02d}.{dt.year}"
        dnm  = DAY_NAMES_UA[dt.weekday()]
        for slot in week_data.get(day_str, {}).get("slots", []):
            if not slot["booked"]:
                continue
            apt = slot["appointment"]
            row_bg = "FFC7CE" if num % 2 else "FFE0E6"
            vals = [
                num, dlbl, dnm, slot["time"],
                apt.get("service", ""), apt.get("name", "—"), apt.get("phone", "—")
            ]
            for ci, v in enumerate(vals, start=1):
                c = ws2.cell(row=num + 1, column=ci, value=v)
                c.fill      = PatternFill("solid", start_color=row_bg)
                c.font      = Font(name="Arial", size=10)
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.border    = _border()
            ws2.row_dimensions[num + 1].height = 22
            num += 1

    if num == 1:
        ws2.merge_cells("A2:G2")
        c = ws2.cell(row=2, column=1, value="— Записів на цей тиждень немає —")
        c.alignment = Alignment(horizontal="center")
        c.font = Font(name="Arial", size=11, italic=True, color="888888")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
