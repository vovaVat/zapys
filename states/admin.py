"""
states/admin.py — FSM-состояния для панели администратора/мастера.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Главная панель
    main_menu = State()

    # Управление расписанием
    schedule_menu = State()
    choosing_schedule_date = State()
    entering_time_slot = State()
    removing_time_slot = State()

    # Быстрая генерация расписания на неделю
    generating_schedule = State()

    # Просмотр и удаление записей
    viewing_all_appointments = State()
    cancelling_client_appointment = State()
