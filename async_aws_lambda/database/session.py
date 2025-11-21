"""
Database session management for Lambda functions.

This module provides async SQLAlchemy session management optimized for Lambda.
Requires sqlalchemy[asyncio] to be installed.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
import os
from typing import Any

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine
    HAS_SQLALCHEMY = True
except ImportError as e:
    raise ImportError(
        "Database support requires 'sqlalchemy[asyncio]'. "
        "Install with: pip install async-aws-lambda[db]"
    ) from e

logger = logging.getLogger(__name__)

# Database engine and session factory
_engine: Any | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None
_initialized = False


async def init_db(
    database_url: str | None = None,
    *,
    pool_size: int = 2,
    max_overflow: int = 3,
    pool_recycle: int = 300,
    pool_pre_ping: bool = True,
    echo: bool = False,
    application_name: str = "async_aws_lambda",
) -> None:
    """
    Initialize database connections for Lambda functions.

    Args:
        database_url: Database connection URL (defaults to DATABASE_URL env var)
        pool_size: Connection pool size (default: 2 for Lambda)
        max_overflow: Maximum overflow connections (default: 3)
        pool_recycle: Connection recycle time in seconds (default: 300)
        pool_pre_ping: Enable connection health checks (default: True)
        echo: Enable SQL query logging (default: False)
        application_name: Application name for database connection (default: "async_aws_lambda")

    Example:
        await init_db("postgresql+asyncpg://user:pass@localhost/db")
        # Or use DATABASE_URL environment variable
        await init_db()
    """
    global _engine, _async_session_maker, _initialized

    if _initialized:
        logger.debug("Database already initialized")
        return

    try:
        # Get database URL from parameter or environment
        db_url = database_url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise ValueError(
                "DATABASE_URL environment variable or database_url parameter required"
            )

        # Create async engine with Lambda-optimized settings
        _engine = create_async_engine(
            db_url,
            echo=echo,
            pool_pre_ping=pool_pre_ping,
            pool_recycle=pool_recycle,
            pool_size=pool_size,
            max_overflow=max_overflow,
            # Lambda-specific connection settings
            connect_args={
                "server_settings": {
                    "timezone": "UTC",
                    "application_name": application_name,
                },
                "timeout": 10,  # Shorter timeout for Lambda
                "command_timeout": 30,  # Shorter command timeout
                # Add connection cleanup settings
                "prepared_statement_cache_size": 0,  # Disable prepared statements
            },
            # Add engine-level cleanup
            pool_reset_on_return="commit",  # Reset connections on return
        )

        # Create session factory with proper cleanup
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,  # Disable autoflush for better control
        )

        # Set timezone to UTC for the connection
        async with _engine.begin() as conn:
            await conn.execute(text("SET timezone = 'UTC'"))
            await conn.execute(
                text(f"SET application_name = '{application_name}'")
            )

        _initialized = True
        logger.info("Database connections initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database connections: {e}")
        raise


async def close_db() -> None:
    """
    Close database connections with proper cleanup.

    This should be called during Lambda cleanup to ensure all connections are closed.
    """
    global _engine, _async_session_maker, _initialized

    try:
        if _engine:
            # Properly dispose of the engine and all connections
            await _engine.dispose()
            _engine = None
            logger.info("Database engine disposed")

        _async_session_maker = None
        _initialized = False
        logger.info("Database connections closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        # Don't re-raise to avoid masking other errors


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for Lambda functions with proper cleanup.

    This is an async context manager that:
    - Initializes database if not already initialized
    - Provides a database session
    - Ensures session is closed on exit
    - Rolls back on exceptions

    Yields:
        AsyncSession: SQLAlchemy async session

    Example:
        async with get_db_session() as session:
            # Use session here
            result = await session.execute(select(User))
    """
    if not _initialized:
        await init_db()

    if _async_session_maker is None:
        raise RuntimeError("Database session maker not initialized")

    session = None
    try:
        session = _async_session_maker()
        # Ensure session uses UTC timezone
        await session.execute(text("SET timezone = 'UTC'"))
        yield session
    except Exception:
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()


async def check_db_health() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        True if database connection is healthy, False otherwise

    Example:
        if await check_db_health():
            print("Database is healthy")
    """
    try:
        if not _engine:
            return False

        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            # Check timezone setting
            result = await conn.execute(text("SHOW timezone"))
            timezone_setting = result.scalar()
            logger.debug(f"Database timezone setting: {timezone_setting}")
        return True

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Register cleanup handler for Lambda lifecycle
try:
    from ..handlers.lifecycle import register_cleanup_handler

    def _cleanup_handler() -> None:
        """
        Synchronous cleanup handler wrapper.

        Handles event loop safely for Python 3.13+ compatibility.
        """
        try:
            # Check if event loop is already running (Python 3.13 best practice)
            try:
                loop = asyncio.get_running_loop()
                # Event loop is running - this shouldn't happen in cleanup handler
                # But if it does, we'll schedule the cleanup (though it may not run)
                logger.warning(
                    "Event loop running during database cleanup - "
                    "cleanup may not complete"
                )
                # Try to create a task (may not execute if loop is shutting down)
                try:
                    loop.create_task(close_db())
                except RuntimeError:
                    # Loop is shutting down - skip async cleanup
                    logger.debug("Event loop shutting down - skipping async cleanup")
            except RuntimeError:
                # No event loop running - safe to create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(close_db())
                finally:
                    loop.close()
                    # Clear the event loop reference
                    asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")

    register_cleanup_handler(_cleanup_handler)
except ImportError:
    # Lifecycle module not available, skip registration
    pass

