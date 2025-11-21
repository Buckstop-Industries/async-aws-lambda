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
from collections.abc import Callable
from typing import Any, TypeVar

from .lifecycle import lambda_lifecycle
from .protocols import DatabaseFactory

T = TypeVar("T", bound=Callable[..., Any])


def lambda_handler(func: T) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """
    Main decorator for async Lambda handlers.

    This decorator:
    - Wraps async handlers to work with synchronous Lambda runtime
    - Manages Lambda lifecycle (cleanup, signals)
    - Handles errors gracefully
    - Works with zero external dependencies

    Args:
        func: Async handler function

    Returns:
        Synchronous Lambda handler compatible with AWS Lambda runtime

    Example:
        @lambda_handler
        async def handler(event, context):
            return {"statusCode": 200, "body": "Hello"}
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
                return await func(event, context)

        return asyncio.run(async_wrapper())

    return wrapper


def with_database(
    func: T | None = None,
    *,
    factory: DatabaseFactory | None = None,
) -> (
    Callable[[T], Callable[[dict[str, Any], Any], dict[str, Any]]]
    | Callable[[dict[str, Any], Any], dict[str, Any]]
):
    """
    Optional decorator for injecting database session into handler.

    This decorator:
    - Injects database session as a parameter (db_session)
    - Manages database connection lifecycle
    - Automatically closes connections on handler completion
    - Requires async-lambda-core[db] extra to be installed

    Args:
        func: Handler function (if used as @with_database)
        factory: Optional custom database factory function

    Returns:
        Decorated handler function

    Example:
        @lambda_handler
        @with_database
        async def handler(event, context, db_session: AsyncSession):
            # Database available here
            return {"statusCode": 200}

        # Or with custom factory
        @lambda_handler
        @with_database(factory=my_db_factory)
        async def handler(event, context, db_session):
            pass
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
                return await handler_func(event, context, *args, **kwargs)

            if factory:
                db_session = await factory()
                try:
                    # Call handler with db_session injected as keyword argument
                    return await handler_func(
                        event, context, *args, db_session=db_session, **kwargs
                    )
                finally:
                    # Cleanup custom session if it has a close method
                    if hasattr(db_session, "close"):
                        await db_session.close()
            else:
                # Use context manager for automatic cleanup
                async with get_db_session() as session:
                    # Call handler with db_session injected as keyword argument
                    return await handler_func(
                        event, context, *args, db_session=session, **kwargs
                    )

        return wrapper

    # Support both @with_database and @with_database(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)


def with_config(
    func: T | None = None,
    *,
    settings_class: type[Any] | None = None,
) -> (
    Callable[[T], Callable[[dict[str, Any], Any], dict[str, Any]]]
    | Callable[[dict[str, Any], Any], dict[str, Any]]
):
    """
    Optional decorator for injecting configuration settings into handler.

    This decorator:
    - Injects settings object as a parameter (settings)
    - Loads configuration from environment variables or secrets
    - Requires async-lambda-core[config] extra for full features

    Args:
        func: Handler function (if used as @with_config)
        settings_class: Optional custom settings class

    Returns:
        Decorated handler function

    Example:
        @lambda_handler
        @with_config
        async def handler(event, context, settings: Settings):
            # Settings available here
            return {"statusCode": 200}
    """
    # Try to import config module (optional dependency)
    try:
        from ..config.settings import Settings, get_settings
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
                settings = get_settings(settings_class)
            else:
                settings = get_settings(Settings)

            # Call handler with settings injected as keyword argument
            # Use signature inspection to inject in the right place
            sig = inspect.signature(handler_func)
            if "settings" in sig.parameters:
                # Inject as keyword argument
                return await handler_func(
                    event, context, *args, settings=settings, **kwargs
                )
            else:
                # Handler doesn't expect settings, call without it
                return await handler_func(event, context, *args, **kwargs)

        return wrapper

    # Support both @with_config and @with_config(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)
