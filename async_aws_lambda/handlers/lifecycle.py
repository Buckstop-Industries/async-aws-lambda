"""
Shared Lambda lifecycle management.

This module provides common lifecycle management functionality for Lambda functions,
including proper resource cleanup, signal handling, and resource management.
"""

import asyncio
import logging
import signal
import sys
import threading
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Add cleanup handling (thread-safe)
_cleanup_registered = False
_cleanup_handlers: list[Callable[[], None]] = []
_cleanup_lock = threading.Lock()


def register_cleanup_handler(handler: Callable[[], None]) -> None:
    """
    Register a cleanup handler to be called on Lambda termination.

    Thread-safe registration for use in multi-threaded environments.

    Args:
        handler: Cleanup function to register (should be synchronous)
    """
    global _cleanup_handlers
    with _cleanup_lock:
        _cleanup_handlers.append(handler)


def _register_lambda_cleanup() -> None:
    """Register cleanup handlers for Lambda termination."""
    global _cleanup_registered
    if _cleanup_registered:
        return

    # Skip signal handler registration during testing
    if "pytest" in sys.modules or "test" in sys.argv[0]:
        logger.debug("Skipping signal handler registration during testing")
        _cleanup_registered = True
        return

    async def cleanup() -> None:
        """Execute all registered cleanup handlers."""
        # Thread-safe access to cleanup handlers
        with _cleanup_lock:
            handlers = list(_cleanup_handlers)
        for handler in handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error during cleanup handler execution: {e}")

    def signal_handler(signum: int, _frame: Any) -> None:
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, initiating cleanup...")
        try:
            # Check if event loop is running (Python 3.13 best practice)
            try:
                # Check if event loop is running
                asyncio.get_running_loop()
                # Event loop is running - schedule cleanup as task
                # Note: This creates a task but signal handler may exit immediately
                # For Lambda, we'll use fallback to sync cleanup
                logger.warning(
                    "Event loop running during signal handler - " "using sync cleanup"
                )
                # Fallback to synchronous cleanup
                with _cleanup_lock:
                    handlers = list(_cleanup_handlers)
                for handler in handlers:
                    try:
                        handler()
                    except Exception as e:
                        logger.error(f"Error during sync cleanup: {e}")
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during signal cleanup: {e}")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    _cleanup_registered = True


@asynccontextmanager
async def lambda_lifecycle() -> AsyncGenerator[None]:
    """
    Context manager for Lambda lifecycle management.

    This context manager:
    - Registers cleanup handlers for proper resource cleanup
    - Ensures cleanup happens even on errors
    - Provides a clean way to manage Lambda lifecycle

    Example:
        async with lambda_lifecycle():
            # Your handler logic here
            pass
    """
    try:
        # Register cleanup handlers
        _register_lambda_cleanup()
        yield
    finally:
        # Execute cleanup handlers (thread-safe access)
        with _cleanup_lock:
            handlers = list(_cleanup_handlers)
        for handler in handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}")


def create_lambda_handler(
    async_handler_func: Callable[..., Any],
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """
    Create a synchronous Lambda handler wrapper with proper cleanup.

    This function wraps an async handler function to make it compatible with
    the AWS Lambda runtime, which expects synchronous handlers.

    Args:
        async_handler_func: The async handler function to wrap

    Returns:
        A synchronous handler function with proper cleanup

    Example:
        async def async_handler(event, context):
            return {"statusCode": 200}

        handler = create_lambda_handler(async_handler)
    """

    def handler(
        event: dict[str, Any],
        context: Any,  # AWS Lambda context object
    ) -> dict[str, Any]:
        """Synchronous Lambda handler wrapper with proper cleanup."""
        try:
            return asyncio.run(async_handler_func(event, context))
        except Exception as e:
            logger.error(f"Lambda handler failed: {e}")
            raise
        finally:
            # Final cleanup attempt
            try:
                # Execute cleanup handlers (thread-safe access)
                with _cleanup_lock:
                    handlers = list(_cleanup_handlers)
                for cleanup_handler in handlers:
                    try:
                        cleanup_handler()
                    except Exception as cleanup_error:
                        logger.error(f"Cleanup handler failed: {cleanup_error}")

                # Note: After asyncio.run() completes, the event loop is closed
                # If any async cleanup is needed, cleanup handlers should handle it
                # No need to create a new event loop here since asyncio.run()
                # already completed and cleaned up the loop
            except Exception as final_cleanup_error:
                logger.error(f"Final cleanup failed: {final_cleanup_error}")

    return handler
