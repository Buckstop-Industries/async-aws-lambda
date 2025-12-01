"""
Database management for Lambda functions.

This module provides optional database support with async SQLAlchemy.
Requires sqlalchemy[asyncio] to be installed.
"""

# Try to import database functionality (requires sqlalchemy)
try:
    from .backends import (
        DatabaseBackend,
        PostgresBackend,
        SQLiteBackend,
        get_backend_for_url,
    )
    from .base import Base
    from .session import check_db_health, close_db, get_db_session, init_db

    HAS_DATABASE = True
    __all__ = [
        "get_db_session",
        "init_db",
        "close_db",
        "check_db_health",
        "Base",
        "DatabaseBackend",
        "PostgresBackend",
        "SQLiteBackend",
        "get_backend_for_url",
    ]
except ImportError:
    HAS_DATABASE = False
    __all__ = []
