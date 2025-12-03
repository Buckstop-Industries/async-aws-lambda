"""
Lambda handler decorators for dependency injection and composition.

This module provides decorators for:
- @lambda_handler - Main decorator for async Lambda handlers
- @with_database - Optional decorator for database session injection
- @with_config - Optional decorator for configuration injection
"""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

from .lifecycle import lambda_lifecycle
from .protocols import DatabaseFactory

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T", bound=Callable[..., Any])


def lambda_handler[**P](
    func: Callable[P, Any],
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """
    Main decorator for async Lambda handlers.

    This decorator wraps async handler functions to make them compatible with
    the AWS Lambda runtime, which expects synchronous handlers. It manages the
    complete Lambda lifecycle including event loop creation, resource cleanup,
    and signal handling.

    Features:
        - Converts async handlers to synchronous Lambda-compatible handlers
        - Manages Lambda lifecycle (cleanup, signals)
        - Handles errors gracefully
        - Works with zero external dependencies
        - Composable with other decorators (@with_database, @with_config)

    Args:
        func: Async handler function that accepts (event, context) and returns
            a response dictionary. The function signature can include additional
            parameters that will be injected by other decorators.

    Returns:
        Synchronous Lambda handler function compatible with AWS Lambda runtime.
        The returned function accepts (event, context) and returns a response
        dictionary.

    Raises:
        TypeError: If the decorated function is not async.

    Note:
        This decorator must be the outermost decorator when used with other
        decorators like @with_database or @with_config. The correct order is:
        @lambda_handler
        @with_database
        @with_config
        async def handler(...):
            ...

    Example:
        Basic usage::

            @lambda_handler
            async def handler(event, context):
                return {"statusCode": 200, "body": "Hello from Lambda!"}

        With other decorators::

            @lambda_handler
            @with_database
            @with_config
            async def handler(event, context, db_session, settings):
                # Use db_session and settings here
                return {"statusCode": 200, "body": "Success"}
    """
    if not inspect.iscoroutinefunction(func):
        raise TypeError(
            f"@lambda_handler can only be applied to async functions. "
            f"{func.__name__} is not async."
        )

    @functools.wraps(func)
    def wrapper(
        event: dict[str, Any],
        context: Any,  # AWS Lambda context object
    ) -> dict[str, Any]:
        """Synchronous wrapper for async handler."""

        async def async_wrapper() -> dict[str, Any]:
            """Execute handler within lifecycle context."""
            async with lambda_lifecycle():
                # Call the handler - other decorators will inject dependencies
                # via kwargs, so we just pass event and context as positional args
                # and let other decorators add their dependencies to kwargs
                result: Any = await func(event, context)  # type: ignore[call-arg, arg-type]
                return cast(dict[str, Any], result)

        return asyncio.run(async_wrapper())

    return wrapper


def with_database[**P](
    func: Callable[P, Any] | None = None,
    *,
    factory: DatabaseFactory | None = None,
) -> (
    Callable[[Callable[P, Any]], Callable[[dict[str, Any], Any], dict[str, Any]]]
    | Callable[[dict[str, Any], Any], dict[str, Any]]
):
    """
    Optional decorator for injecting database session into handler.

    This decorator automatically injects a database session (AsyncSession) into
    your handler function. It manages the complete database connection lifecycle,
    including initialization, connection pooling, and cleanup.

    Features:
        - Injects database session as a parameter (db_session)
        - Manages database connection lifecycle
        - Automatically closes connections on handler completion
        - Lambda-optimized connection pooling
        - Supports custom database factories

    Args:
        func: Handler function (if used as @with_database without parentheses).
            This parameter is used internally for decorator syntax support.
        factory: Optional custom database factory function. If provided, this
            async callable will be used to create database sessions instead of
            the default session factory. The factory must return a database
            session object with a `close()` method for cleanup.

    Returns:
        Decorated handler function that accepts (event, context, db_session, ...)
        where db_session is automatically injected.

    Raises:
        ImportError: If the database extra is not installed. Install with:
            pip install async-aws-lambda[db]
        TypeError: If the decorated function is not async.
        ValueError: If DATABASE_URL is not set and database_url parameter is
            not provided to init_db().

    Note:
        - The handler function must accept a parameter named `db_session` to
          receive the injected session. If the parameter is not present, the
          decorator will still work but no session will be injected.
        - Database connections are automatically initialized on first use.
        - Connections are automatically closed after handler execution.
        - This decorator must be placed between @lambda_handler and the handler
          function definition.

    Example:
        Basic usage with default database connection::

            from sqlalchemy.ext.asyncio import AsyncSession

            @lambda_handler
            @with_database
            async def handler(event, context, db_session: AsyncSession):
                result = await db_session.execute(text("SELECT 1"))
                return {"statusCode": 200, "body": str(result.scalar())}

        With custom database factory::

            async def my_db_factory():
                # Custom database connection logic
                engine = create_async_engine("custom://...")
                return AsyncSession(engine)

            @lambda_handler
            @with_database(factory=my_db_factory)
            async def handler(event, context, db_session):
                # Use custom session here
                return {"statusCode": 200}

        Environment variable setup::

            # Set DATABASE_URL environment variable
            export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
    """
    # Try to import database module (optional dependency)
    try:
        from ..database import get_db_session, init_db
    except ImportError:
        raise ImportError(
            "Database support requires 'async-aws-lambda[db]' extra. "
            "Install with: pip install async-aws-lambda[db]"
        )

    def decorator(handler_func: T) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
        """Inner decorator function."""
        if not inspect.iscoroutinefunction(handler_func):
            raise TypeError(
                f"@with_database can only be applied to async functions. "
                f"{handler_func.__name__} is not async."
            )

        @functools.wraps(handler_func)
        async def wrapper(
            event: dict[str, Any],
            context: Any,
            *args: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Wrapper that injects database session."""
            # Initialize database if needed
            await init_db()

            # Use custom factory or default
            sig = inspect.signature(handler_func)
            if "db_session" not in sig.parameters:
                # Handler doesn't expect db_session, call without it
                # Still need to cleanup database resources
                try:
                    no_db_result: Any = await handler_func(
                        event, context, *args, **kwargs
                    )
                    return cast(dict[str, Any], no_db_result)
                finally:
                    # Ensure database cleanup happens even when db_session is not used
                    # This is critical for backends like SQLite that use background
                    # threads
                    from ..database import close_db

                    try:
                        await close_db()
                    except Exception as cleanup_error:
                        logger.debug(f"Error during database cleanup: {cleanup_error}")

            if factory:
                db_session = await factory()
                try:
                    # Call handler with db_session injected as keyword argument
                    factory_result: Any = await handler_func(
                        event, context, *args, db_session=db_session, **kwargs
                    )
                    return cast(dict[str, Any], factory_result)
                finally:
                    # Cleanup custom session if it has a close method
                    if hasattr(db_session, "close"):
                        await db_session.close()
            else:
                # Use context manager for automatic cleanup
                try:
                    async with get_db_session() as session:
                        # Call handler with db_session injected as keyword argument
                        session_result: Any = await handler_func(
                            event, context, *args, db_session=session, **kwargs
                        )
                        return cast(dict[str, Any], session_result)
                finally:
                    # Ensure database cleanup happens while event loop is still running
                    # This is critical for backends like SQLite that use background
                    # threads
                    from ..database import close_db

                    try:
                        await close_db()
                    except Exception as cleanup_error:
                        logger.debug(f"Error during database cleanup: {cleanup_error}")

        return wrapper  # type: ignore[return-value]

    # Support both @with_database and @with_database(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)


def with_config[**P](
    func: Callable[P, Any] | None = None,
    *,
    settings_class: type[Any] | None = None,
) -> (
    Callable[[Callable[P, Any]], Callable[[dict[str, Any], Any], dict[str, Any]]]
    | Callable[[dict[str, Any], Any], dict[str, Any]]
):
    """
    Optional decorator for injecting configuration settings into handler.

    This decorator automatically injects a settings object (Pydantic Settings) into
    your handler function. Settings are loaded from environment variables and
    cached for performance.

    Features:
        - Injects settings object as a parameter (settings)
        - Loads configuration from environment variables
        - Type-safe configuration via Pydantic
        - Settings are cached for performance
        - Supports custom settings classes

    Args:
        func: Handler function (if used as @with_config without parentheses).
            This parameter is used internally for decorator syntax support.
        settings_class: Optional custom settings class that extends the base
            Settings class. If provided, this class will be instantiated instead
            of the default Settings class. The class must be a subclass of
            async_aws_lambda.config.Settings (which extends
            pydantic_settings.BaseSettings).

    Returns:
        Decorated handler function that accepts (event, context, settings, ...)
        where settings is automatically injected.

    Raises:
        ImportError: If the config extra is not installed. Install with:
            pip install async-aws-lambda[config]
        TypeError: If the decorated function is not async.
        ValidationError: If required settings fields are missing or invalid
            (raised by Pydantic during settings instantiation).

    Note:
            - The handler function must accept a parameter named `settings` to
              receive the injected settings object. If the parameter is not
              present, the decorator will still work but no settings will be
              injected.
        - Settings are cached per settings class to avoid re-reading environment
          variables on every invocation.
        - This decorator must be placed between @lambda_handler and the handler
          function definition.

    Example:
        Basic usage with default Settings::

            from async_aws_lambda.config import Settings

            @lambda_handler
            @with_config
            async def handler(event, context, settings: Settings):
                # Access settings here
                return {"statusCode": 200}

        With custom settings class::

            from async_aws_lambda.config import Settings

            class MySettings(Settings):
                API_KEY: str
                DEBUG: bool = False
                DATABASE_URL: str

            @lambda_handler
            @with_config(settings_class=MySettings)
            async def handler(event, context, settings: MySettings):
                if settings.DEBUG:
                    print(f"API Key: {settings.API_KEY}")
                return {"statusCode": 200}

        Environment variable setup::

            # Set environment variables
            export API_KEY="your-api-key"
            export DEBUG="true"
            export DATABASE_URL="postgresql://..."
    """
    # Try to import config module (optional dependency)
    try:
        from ..config.settings import get_settings
    except ImportError:
        raise ImportError(
            "Configuration support requires 'async-aws-lambda[config]' extra. "
            "Install with: pip install async-aws-lambda[config]"
        )

    def decorator(handler_func: T) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
        """Inner decorator function."""
        if not inspect.iscoroutinefunction(handler_func):
            raise TypeError(
                f"@with_config can only be applied to async functions. "
                f"{handler_func.__name__} is not async."
            )

        @functools.wraps(handler_func)
        async def wrapper(
            event: dict[str, Any],
            context: Any,
            *args: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Wrapper that injects settings."""
            # Get settings (use custom class or default)
            if settings_class:
                settings = get_settings(settings_class)  # type: ignore[arg-type]
            else:
                settings = get_settings()

            # Call handler with settings injected as keyword argument
            # Use signature inspection to inject in the right place
            sig = inspect.signature(handler_func)
            if "settings" in sig.parameters:
                # Inject as keyword argument
                with_settings_result: Any = await handler_func(
                    event, context, *args, settings=settings, **kwargs
                )
                return cast(dict[str, Any], with_settings_result)
            else:
                # Handler doesn't expect settings, call without it
                no_settings_result: Any = await handler_func(
                    event, context, *args, **kwargs
                )
                return cast(dict[str, Any], no_settings_result)

        return wrapper  # type: ignore[return-value]

    # Support both @with_config and @with_config(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)
