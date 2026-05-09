# handlers/__init__.py
from .start import router as start_router
from .booking import router as booking_router
from .my_appointments import router as my_appointments_router
from .admin import router as admin_router

__all__ = [
    "start_router",
    "booking_router",
    "my_appointments_router",
    "admin_router",
]
