# routes/__init__.py
# Package initialization for routes module

from .auth import auth_bp
from .flights import flights_bp
from .booking import booking_bp
from .management import management_bp
from .debug import debug_bp

__all__ = ['auth_bp', 'flights_bp', 'booking_bp', 'management_bp', 'debug_bp']
