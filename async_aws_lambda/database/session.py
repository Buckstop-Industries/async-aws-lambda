"""
Database session management for Lambda functions.

This module provides async SQLAlchemy session management optimized for Lambda.
Requires sqlalchemy[asyncio] to be installed.
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    HAS_SQLALCHEMY = True
except ImportError as e:
    raise ImportError(
        "Database support requires 'sqlalchemy[asyncio]'. "
        "Install with: pip install async-aws-lambda[db]"
    ) from e

from .backends import DatabaseBackend, get_backend_for_url

logger = logging.getLogger(__name__)

# Database engine and session factory
_engine: Any | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None
_backend: DatabaseBackend | None = None
_initialized = False


async def init_db(
    database_url: str | None = None,
    *,
    backend: DatabaseBackend | None = None,
    pool_size: int = 2,
    max_overflow: int = 3,
    pool_recycle: int = 300,
    pool_pre_ping: bool = True,
    echo: bool = False,
    application_name: str = "async_aws_lambda",
) -> None:
    """
    Initialize database connections for Lambda functions.

    This function creates and configures the database engine and session factory
    with Lambda-optimized settings. It is automatically called by the
    @with_database decorator, but can also be called manually for advanced use cases.

    The function is idempotent - calling it multiple times will only initialize
    once. Subsequent calls are ignored.

    Args:
        database_url: Database connection URL. Must be a valid SQLAlchemy
            async connection string (e.g., "postgresql+asyncpg://..." or
            "sqlite+aiosqlite:///..."). Defaults to DATABASE_URL environment
            variable if not provided.
        backend: Optional database backend instance. If not provided, the backend
            will be auto-detected from the database_url. Use this parameter to
            explicitly specify a backend or use a custom backend implementation.
        pool_size: Connection pool size. Default is 2, which is optimal for
            Lambda's concurrent execution model. Each Lambda instance typically
            handles one request at a time, so a small pool is sufficient.
        max_overflow: Maximum overflow connections beyond pool_size. Default is 3.
            Total maximum connections = pool_size + max_overflow = 5 by default.
        pool_recycle: Connection recycle time in seconds. Default is 300 (5 minutes).
            Connections older than this will be recycled to prevent stale connections.
        pool_pre_ping: Enable connection health checks. Default is True. When
            enabled, connections are checked before use to ensure they're still
            valid. Recommended for production to handle database restarts gracefully.
        echo: Enable SQL query logging. Default is False. When True, all SQL
            queries will be logged. Useful for debugging but should be disabled
            in production for performance.
        application_name: Application name for database connection. Default is
            "async_aws_lambda". This name appears in database connection logs
            and can help identify connections from this application. Must contain
            only alphanumeric characters, underscores, hyphens, dots, and spaces.
            Maximum length is 63 characters.

    Returns:
        None

    Raises:
        ValueError: If database_url is not provided and DATABASE_URL environment
            variable is not set.
        ValueError: If application_name contains invalid characters or exceeds
            63 characters.
        ImportError: If SQLAlchemy is not installed. Install with:
            pip install async-aws-lambda[db]
        Exception: Any exception raised during database engine creation will
            be logged and re-raised.

    Note:
        - This function is automatically called by @with_database decorator
        - The function is idempotent - safe to call multiple times
        - Database connections are optimized for Lambda's execution model
        - Connection pooling settings are tuned for serverless workloads

    Example:
        Initialize with explicit URL::

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

        Use environment variable::

            # Set DATABASE_URL environment variable
            export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
            await init_db()

        With custom settings::

            await init_db(
                database_url="postgresql+asyncpg://...",
                pool_size=5,
                max_overflow=10,
                pool_recycle=600,
                echo=True  # Enable SQL logging
            )

        With explicit backend::

            from async_aws_lambda.database.backends import SQLiteBackend

            await init_db(
                "sqlite+aiosqlite:///path/to/db",
                backend=SQLiteBackend()
            )
    """
    global _engine, _async_session_maker, _backend, _initialized

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

        # Get or detect backend
        if backend is None:
            _backend = get_backend_for_url(db_url)
        else:
            _backend = backend

        # Get backend-specific connection arguments
        connect_args = _backend.get_connect_args(
            timeout=10,
            command_timeout=30,
            application_name=application_name,
        )

        # Get backend-specific engine keyword arguments
        engine_kwargs = _backend.get_engine_kwargs(
            echo=echo,
            pool_pre_ping=pool_pre_ping,
            pool_recycle=pool_recycle,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
        engine_kwargs["connect_args"] = connect_args

        # Create async engine with Lambda-optimized settings
        _engine = create_async_engine(db_url, **engine_kwargs)

        # Create session factory with proper cleanup
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,  # Disable autoflush for better control
        )

        # Execute backend-specific initialization queries
        init_queries = _backend.get_initialization_queries(
            application_name=application_name
        )
        if init_queries:
            async with _engine.begin() as conn:
                for query in init_queries:
                    await conn.execute(text(query))

        _initialized = True
        logger.info("Database connections initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database connections: {e}")
        raise


async def close_db() -> None:
    """
    Close database connections with proper cleanup.

    This function disposes of the database engine and closes all connections in
    the pool. It performs backend-specific cleanup to ensure all resources are
    properly released, including waiting for background threads (e.g., SQLite).

    This function is automatically called by the Lambda lifecycle manager during
    handler cleanup, but can also be called manually if needed.

    Args:
        None

    Returns:
        None

    Raises:
        Exception: Errors during cleanup are logged but not re-raised to avoid
            masking other errors during Lambda shutdown.

    Note:
        - This function is automatically called during Lambda cleanup
        - Safe to call multiple times (idempotent)
        - Must be called while the event loop is still running for proper
          async cleanup
        - Backend-specific cleanup (e.g., SQLite thread management) is handled
          automatically

    Example:
        Manual cleanup::

            async def handler(event, context):
                await init_db()
                # Use database...
                await close_db()  # Manual cleanup (usually not needed)
    """
    global _engine, _async_session_maker, _backend, _initialized

    try:
        if _engine:
            # Properly dispose of the engine and all connections
            # This must happen while the event loop is still running
            try:
                # First, close all connections properly while event loop is active
                # This ensures background threads can complete their work
                await _engine.dispose(close=True)

                # After disposal, perform backend-specific cleanup
                # This waits for any background threads to complete
                if _backend:
                    try:
                        _backend.cleanup_before_dispose(_engine)
                    except Exception as post_cleanup_error:
                        logger.debug(
                            f"Error during post-disposal cleanup: {post_cleanup_error}"
                        )

            except (asyncio.CancelledError, RuntimeError) as cleanup_error:
                # Expected during event loop shutdown - tasks get cancelled
                # RuntimeError can occur if event loop is already closed
                logger.debug(
                    f"Cleanup cancelled or event loop closed "
                    f"(expected during shutdown): {cleanup_error}"
                )
            except Exception as dispose_error:
                # Other errors during disposal
                logger.debug(f"Error during engine disposal: {dispose_error}")
            finally:
                _engine = None
                logger.info("Database engine disposed")

        _async_session_maker = None
        _backend = None
        _initialized = False
        logger.info("Database connections closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        # Don't re-raise to avoid masking other errors


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    Get database session for Lambda functions with proper cleanup.

    This is an async context manager that provides a database session with
    automatic lifecycle management. The session is automatically closed when
    exiting the context, and transactions are rolled back on exceptions.

    Features:
        - Initializes database if not already initialized
        - Provides a database session from the connection pool
        - Ensures session is closed on exit
        - Rolls back transactions on exceptions
        - Executes backend-specific session queries

    Yields:
        AsyncSession: SQLAlchemy async session ready for use. The session is
            automatically closed when exiting the context manager.

    Raises:
        RuntimeError: If the database session maker is not initialized. This
            typically means init_db() was not called or failed.
        ValueError: If DATABASE_URL is not set and database_url parameter was
            not provided to init_db().

    Note:
        - This function is automatically used by @with_database decorator
        - Sessions are obtained from the connection pool
        - Uncommitted transactions are automatically rolled back on exceptions
        - Sessions are automatically closed when exiting the context

    Example:
        Basic usage::

            async with get_db_session() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()

        With exception handling::

            async with get_db_session() as session:
                try:
                    # Perform database operations
                    await session.execute(insert(User).values(name="John"))
                    await session.commit()
                except Exception:
                    # Transaction automatically rolled back
                    raise

        Using with SQLAlchemy models::

            from sqlalchemy import select
            from my_models import User

            async with get_db_session() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
    """
    if not _initialized:
        await init_db()

    if _async_session_maker is None:
        raise RuntimeError("Database session maker not initialized")

    session = None
    try:
        session = _async_session_maker()
        # Execute backend-specific session queries
        if _backend:
            session_queries = _backend.get_session_queries()
            for query in session_queries:
                await session.execute(text(query))
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

    This function performs a simple health check query against the database
    to verify that connections are working properly. It's useful for Lambda
    health checks or monitoring.

    The health check executes a backend-specific query (typically "SELECT 1")
    to verify connectivity and responsiveness.

    Args:
        None

    Returns:
        True if the database connection is healthy and responsive, False
        otherwise. Returns False if the database is not initialized or if
        the health check query fails.

    Note:
        - Returns False if database is not initialized
        - Returns False if health check query fails
        - Does not raise exceptions - returns False on any error
        - Useful for Lambda health check endpoints

    Example:
        Basic health check::

            if await check_db_health():
                return {"statusCode": 200, "body": "Healthy"}
            else:
                return {"statusCode": 503, "body": "Database unavailable"}

        In a Lambda handler::

            @lambda_handler
            async def health_check(event, context):
                db_healthy = await check_db_health()
                return {
                    "statusCode": 200 if db_healthy else 503,
                    "body": {"database": "healthy" if db_healthy else "unhealthy"}
                }
    """
    try:
        if not _engine or not _backend:
            return False

        async with _engine.begin() as conn:
            health_query = _backend.get_health_check_query()
            await conn.execute(text(health_query))
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
        Properly handles SQLite's background threads to avoid event loop closure errors.
        """
        try:
            # Check if event loop is already running (Python 3.13 best practice)
            try:
                loop = asyncio.get_running_loop()
                # Event loop is running - this shouldn't happen in cleanup handler
                # But if it does, we can't use run_until_complete (would deadlock)
                # Instead, schedule the cleanup task and hope it completes
                logger.warning(
                    "Event loop running during database cleanup - "
                    "scheduling cleanup task (may not complete)"
                )
                # Schedule cleanup as a task - it may not complete if loop is
                # shutting down
                try:
                    task = loop.create_task(close_db())
                    # Can't wait for it here without deadlocking
                    # The task will run if the loop continues, otherwise it will be
                    # cancelled
                    logger.debug("Database cleanup task scheduled")
                except RuntimeError:
                    # Loop is shutting down - skip async cleanup
                    logger.debug("Event loop shutting down - skipping async cleanup")
            except RuntimeError:
                # No event loop running - safe to create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Run cleanup with a timeout to avoid hanging
                    # Use a shorter timeout and handle all exceptions gracefully
                    cleanup_task = asyncio.wait_for(close_db(), timeout=1.0)
                    loop.run_until_complete(cleanup_task)
                except (TimeoutError, asyncio.CancelledError, RuntimeError):
                    # Expected during shutdown:
                    # - TimeoutError: Cleanup took too long
                    # - CancelledError: Task was cancelled
                    # - RuntimeError: Event loop is closed
                    # These are all acceptable during Lambda shutdown
                    logger.debug(
                        "Database cleanup interrupted during shutdown (expected)"
                    )
                except Exception as cleanup_error:
                    # Log but don't fail - we're shutting down
                    logger.debug(
                        f"Database cleanup error (non-critical during shutdown): "
                        f"{cleanup_error}"
                    )
                finally:
                    # Ensure loop is properly closed
                    try:
                        # Cancel any remaining tasks
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        # Run until all tasks are cancelled
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except Exception:
                        pass
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
