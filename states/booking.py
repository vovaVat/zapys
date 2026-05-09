"""
states/booking.py — FSM-состояния для процесса записи клиента.
Каждое состояние соответствует одному шагу диалога.
"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    # Шаг 1: Выбор услуги
    choosing_service = State()

    # Шаг 2: Выбор даты
    choosing_date = State()

    # Шаг 3: Выбор времени
    choosing_time = State()

    # Шаг 4: Ввод имени
    entering_name = State()

    # Шаг 5: Ввод телефона
    entering_phone = State()

    # Шаг 6: Подтверждение записи
    confirming = State()

    # Шаг: Просмотр/отмена своих записей
    viewing_appointments = State()

    # Шаг: Выбор записи для отмены
    cancelling_appointment = State()
