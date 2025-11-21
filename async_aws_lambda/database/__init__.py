"""
Database management for Lambda functions.

This module provides optional database support with async SQLAlchemy.
Requires sqlalchemy[asyncio] to be installed.
"""

# Try to import database functionality (requires sqlalchemy)
try:
    from .session import (
        get_db_session,
        init_db,
        close_db,
        check_db_health,
    )
    from .base import Base

    HAS_DATABASE = True
    __all__ = [
        "get_db_session",
        "init_db",
        "close_db",
        "check_db_health",
        "Base",
    ]
except ImportError:
    HAS_DATABASE = False
    __all__ = []

