"""
Database backend abstractions for different database engines.

This module provides abstract base classes and implementations for
PostgreSQL, SQLite, and other database backends.
"""

import re
from abc import ABC, abstractmethod
from typing import Any


def _validate_application_name(name: str) -> str:
    """
    Validate and sanitize application name to prevent SQL injection.

    Args:
        name: Application name to validate

    Returns:
        Validated application name

    Raises:
        ValueError: If application name contains invalid characters
    """
    # Allow alphanumeric, underscore, hyphen, dot, and space
    # Max length of 63 characters (PostgreSQL identifier limit)
    if not re.match(r"^[a-zA-Z0-9_\-\. ]{1,63}$", name):
        raise ValueError(
            f"Invalid application_name: {name}. "
            "Must contain only alphanumeric characters, underscores, hyphens, "
            "dots, and spaces. Maximum length is 63 characters."
        )
    # Escape single quotes for SQL string literal
    return name.replace("'", "''")


class DatabaseBackend(ABC):
    """
    Abstract base class for database backend implementations.

    Subclasses must implement methods to provide database-specific
    connection arguments, initialization queries, and health check queries.
    """

    @abstractmethod
    def get_connect_args(self, **kwargs: Any) -> dict[str, Any]:
        """
        Get database-specific connection arguments.

        Args:
            **kwargs: Additional keyword arguments (e.g., timeout, application_name)

        Returns:
            Dictionary of connection arguments for create_async_engine
        """
        ...

    @abstractmethod
    def get_initialization_queries(self, **kwargs: Any) -> list[str]:
        """
        Get queries to execute during database initialization.

        Args:
            **kwargs: Additional keyword arguments (e.g., application_name)

        Returns:
            List of SQL queries to execute during init_db
        """
        ...

    @abstractmethod
    def get_session_queries(self, **kwargs: Any) -> list[str]:
        """
        Get queries to execute for each new session.

        Args:
            **kwargs: Additional keyword arguments

        Returns:
            List of SQL queries to execute for each session
        """
        ...

    @abstractmethod
    def get_health_check_query(self) -> str:
        """
        Get query to use for database health checks.

        Returns:
            SQL query string for health checks
        """
        ...

    @abstractmethod
    def supports_connection_pooling(self) -> bool:
        """
        Indicate whether this backend supports connection pooling.

        Returns:
            True if connection pooling parameters should be used, False otherwise
        """
        ...

    @abstractmethod
    def get_engine_kwargs(
        self,
        *,
        echo: bool = False,
        pool_pre_ping: bool = True,
        pool_recycle: int = 300,
        pool_size: int = 2,
        max_overflow: int = 3,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Get engine-specific keyword arguments for create_async_engine.

        Args:
            echo: Enable SQL query logging
            pool_pre_ping: Enable connection health checks
            pool_recycle: Connection recycle time in seconds
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of engine keyword arguments
        """
        ...

    def cleanup_before_dispose(self, engine: Any) -> None:
        """
        Perform any backend-specific cleanup before engine disposal.

        This is called synchronously before async engine disposal to handle
        backends that may have issues with async cleanup (e.g., SQLite with
        background threads).

        Args:
            engine: The SQLAlchemy async engine instance
        """
        # Default implementation does nothing - subclasses can override
        pass


class PostgresBackend(DatabaseBackend):
    """
    PostgreSQL database backend implementation.

    This backend provides PostgreSQL-specific optimizations and configurations
    for async SQLAlchemy connections. It's automatically selected when using
    connection URLs that start with "postgresql://", "postgresql+", "postgres://",
    or "postgres+".

    Features:
        - Optimized connection pooling for PostgreSQL
        - Timezone configuration (UTC)
        - Application name tracking
        - Connection health checks via pre-ping
        - Prepared statement cache disabled (Lambda optimization)

    Example:
        Explicit usage::

            from async_aws_lambda.database.backends import PostgresBackend

            await init_db(
                "postgresql+asyncpg://user:pass@localhost/db",
                backend=PostgresBackend()
            )

        Auto-detection (default)::

            # Automatically uses PostgresBackend
            await init_db("postgresql+asyncpg://user:pass@localhost/db")
    """

    def get_connect_args(
        self,
        *,
        timeout: int = 10,
        command_timeout: int = 30,
        application_name: str = "async_aws_lambda",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Get PostgreSQL-specific connection arguments.

        Args:
            timeout: Connection timeout in seconds
            command_timeout: Command timeout in seconds
            application_name: Application name for PostgreSQL (validated for safety)
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of PostgreSQL connection arguments

        Raises:
            ValueError: If application_name contains invalid characters
        """
        # Validate application_name to prevent injection via server_settings
        validated_name = _validate_application_name(application_name)
        return {
            "server_settings": {
                "timezone": "UTC",
                "application_name": validated_name,
            },
            "timeout": timeout,
            "command_timeout": command_timeout,
            "prepared_statement_cache_size": 0,  # Disable prepared statements
        }

    def get_initialization_queries(
        self, *, application_name: str = "async_aws_lambda", **kwargs: Any
    ) -> list[str]:
        """
        Get PostgreSQL initialization queries.

        Args:
            application_name: Application name for PostgreSQL (validated for safety)
            **kwargs: Additional keyword arguments

        Returns:
            List of PostgreSQL initialization queries

        Raises:
            ValueError: If application_name contains invalid characters
        """
        # Validate and sanitize application_name to prevent SQL injection
        validated_name = _validate_application_name(application_name)
        # Properly escape single quotes in SQL string literal
        escaped_name = validated_name.replace("'", "''")
        return [
            "SET timezone = 'UTC'",
            f"SET application_name = '{escaped_name}'",
        ]

    def get_session_queries(self, **kwargs: Any) -> list[str]:
        """
        Get PostgreSQL session queries.

        Args:
            **kwargs: Additional keyword arguments

        Returns:
            List of PostgreSQL session queries
        """
        return ["SET timezone = 'UTC'"]

    def get_health_check_query(self) -> str:
        """
        Get PostgreSQL health check query.

        Returns:
            PostgreSQL health check query
        """
        return "SELECT 1"

    def supports_connection_pooling(self) -> bool:
        """
        PostgreSQL supports connection pooling.

        Returns:
            True
        """
        return True

    def get_engine_kwargs(
        self,
        *,
        echo: bool = False,
        pool_pre_ping: bool = True,
        pool_recycle: int = 300,
        pool_size: int = 2,
        max_overflow: int = 3,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Get PostgreSQL engine keyword arguments.

        Args:
            echo: Enable SQL query logging
            pool_pre_ping: Enable connection health checks
            pool_recycle: Connection recycle time in seconds
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of PostgreSQL engine keyword arguments
        """
        return {
            "echo": echo,
            "pool_pre_ping": pool_pre_ping,
            "pool_recycle": pool_recycle,
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_reset_on_return": "commit",
        }


class SQLiteBackend(DatabaseBackend):
    """
    SQLite database backend implementation.

    This backend provides SQLite-specific optimizations and configurations
    for async SQLAlchemy connections using aiosqlite. It's automatically
    selected when using connection URLs that start with "sqlite://", "sqlite+",
    or "sqlite3://".

    Features:
        - Write-Ahead Logging (WAL) mode for better concurrency
        - Foreign key constraints enabled
        - Optimized for Lambda's single-threaded execution model
        - Proper cleanup of background threads

    Note:
        - SQLite does not support connection pooling parameters
        - Uses StaticPool for connection management
        - Background threads are properly managed during cleanup

    Example:
        Explicit usage::

            from async_aws_lambda.database.backends import SQLiteBackend

            await init_db(
                "sqlite+aiosqlite:///path/to/db",
                backend=SQLiteBackend()
            )

        Auto-detection (default)::

            # Automatically uses SQLiteBackend
            await init_db("sqlite+aiosqlite:///path/to/db")
    """

    def get_connect_args(
        self,
        *,
        timeout: int = 10,
        check_same_thread: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Get SQLite-specific connection arguments.

        Args:
            timeout: Connection timeout in seconds
            check_same_thread: Whether to check same thread (default: False for async)
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of SQLite connection arguments
        """
        return {
            "timeout": timeout,
            "check_same_thread": check_same_thread,
        }

    def get_initialization_queries(self, **kwargs: Any) -> list[str]:
        """
        Get SQLite initialization queries.

        SQLite doesn't require initialization queries, but we can set
        some useful pragmas for better behavior.

        Args:
            **kwargs: Additional keyword arguments

        Returns:
            List of SQLite initialization queries
        """
        return [
            "PRAGMA foreign_keys = ON",
            "PRAGMA journal_mode = WAL",  # Write-Ahead Logging for better concurrency
        ]

    def get_session_queries(self, **kwargs: Any) -> list[str]:
        """
        Get SQLite session queries.

        Args:
            **kwargs: Additional keyword arguments

        Returns:
            List of SQLite session queries (empty for SQLite)
        """
        return []

    def get_health_check_query(self) -> str:
        """
        Get SQLite health check query.

        Returns:
            SQLite health check query
        """
        return "SELECT 1"

    def supports_connection_pooling(self) -> bool:
        """
        SQLite does not support connection pooling parameters.

        Returns:
            False
        """
        return False

    def get_engine_kwargs(
        self,
        *,
        echo: bool = False,
        pool_pre_ping: bool = True,
        pool_recycle: int = 300,
        pool_size: int = 2,
        max_overflow: int = 3,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Get SQLite engine keyword arguments.

        SQLite does not support connection pooling, so pooling parameters are excluded.

        Args:
            echo: Enable SQL query logging
            pool_pre_ping: Ignored for SQLite
            pool_recycle: Ignored for SQLite
            pool_size: Ignored for SQLite
            max_overflow: Ignored for SQLite
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary of SQLite engine keyword arguments (without pooling)
        """
        return {
            "echo": echo,
        }

    def cleanup_before_dispose(self, engine: Any) -> None:
        """
        Cleanup SQLite connections before disposal.

        SQLite with aiosqlite uses background threads. This method ensures
        all connections are closed synchronously and waits for background threads
        to complete before the event loop closes.

        Args:
            engine: The SQLAlchemy async engine instance
        """
        import threading
        import time

        try:
            # Get the sync engine and pool
            sync_engine = engine.sync_engine
            if hasattr(sync_engine, "pool") and sync_engine.pool:
                pool = sync_engine.pool

                # Get all active connections and close them synchronously
                # This prevents background threads from trying to close them later
                try:
                    # For StaticPool (used by SQLite), get all connections
                    if hasattr(pool, "_conn") and pool._conn:
                        # Close the connection synchronously
                        conn = pool._conn
                        if hasattr(conn, "close"):
                            try:
                                conn.close()
                            except Exception:
                                pass
                except Exception:
                    pass

                # Dispose the pool to signal cleanup
                try:
                    pool.dispose()
                except Exception:
                    pass

                # Wait for aiosqlite background threads to complete
                # These threads handle async operations and need time to finish
                aiosqlite_threads = [
                    t
                    for t in threading.enumerate()
                    if t.is_alive()
                    and ("aiosqlite" in t.name.lower() or "Thread-" in t.name)
                ]

                # Wait up to 2 seconds for threads to complete
                # Check every 0.1 seconds
                for _ in range(20):
                    aiosqlite_threads = [
                        t
                        for t in threading.enumerate()
                        if t.is_alive()
                        and ("aiosqlite" in t.name.lower() or "Thread-" in t.name)
                    ]
                    if not aiosqlite_threads:
                        break
                    time.sleep(0.1)
        except Exception:
            # Ignore errors during cleanup - we're shutting down
            pass


def get_backend_for_url(database_url: str) -> DatabaseBackend:
    """
    Detect and return the appropriate database backend for a given URL.

    This function analyzes the database connection URL and returns the
    appropriate DatabaseBackend instance. It supports PostgreSQL and SQLite
    backends, with automatic detection based on URL scheme.

    Supported URL schemes:
        - PostgreSQL: "postgresql://", "postgresql+", "postgres://", "postgres+"
        - SQLite: "sqlite://", "sqlite+", "sqlite3://"

    Args:
        database_url: Database connection URL. Must be a valid SQLAlchemy
            connection string. The scheme (protocol) part of the URL determines
            which backend is selected.

    Returns:
        Appropriate DatabaseBackend instance:
            - PostgresBackend for PostgreSQL URLs
            - SQLiteBackend for SQLite URLs

    Raises:
        ValueError: If the database URL scheme is not supported. Currently
            only PostgreSQL and SQLite are supported.

    Note:
        - URL matching is case-insensitive
        - The function only checks the URL scheme, not the full URL validity
        - For custom backends, pass the backend instance directly to init_db()

    Example:
        Auto-detect PostgreSQL backend::

            backend = get_backend_for_url("postgresql+asyncpg://user:pass@localhost/db")
            assert isinstance(backend, PostgresBackend)

        Auto-detect SQLite backend::

            backend = get_backend_for_url("sqlite+aiosqlite:///path/to/db")
            assert isinstance(backend, SQLiteBackend)

        Used automatically by init_db()::

            # init_db() calls this function internally
            await init_db("postgresql+asyncpg://...")  # Uses PostgresBackend
            await init_db("sqlite+aiosqlite:///...")   # Uses SQLiteBackend

        Unsupported URL::

            >>> get_backend_for_url("mysql://...")
            ValueError: Unsupported database URL scheme: mysql://...
    """
    url_lower = database_url.lower()

    if url_lower.startswith(
        ("postgresql://", "postgresql+", "postgres://", "postgres+")
    ):
        return PostgresBackend()
    elif url_lower.startswith(("sqlite://", "sqlite+", "sqlite3://")):
        return SQLiteBackend()
    else:
        raise ValueError(
            f"Unsupported database URL scheme: {database_url}. "
            "Supported schemes: postgresql+asyncpg, sqlite+aiosqlite"
        )
