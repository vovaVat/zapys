# keyboards/__init__.py
from .user_kb import (
    main_menu_kb,
    services_kb,
    dates_kb,
    times_kb,
    name_kb,
    phone_kb,
    phone_request_kb,
    remove_reply_kb,
    confirm_kb,
    appointments_kb,
    cancel_appointment_kb,
    back_kb,
)
from .admin_kb import (
    admin_main_kb,
    admin_schedule_kb,
    admin_appointments_kb,
    admin_cancel_appointment_kb,
    admin_generate_week_kb,
)

__all__ = [
    "main_menu_kb",
    "services_kb",
    "dates_kb",
    "times_kb",
    "name_kb",
    "phone_kb",
    "phone_request_kb",
    "remove_reply_kb",
    "confirm_kb",
    "appointments_kb",
    "cancel_appointment_kb",
    "back_kb",
    "admin_main_kb",
    "admin_schedule_kb",
    "admin_appointments_kb",
    "admin_cancel_appointment_kb",
    "admin_generate_week_kb",
]
