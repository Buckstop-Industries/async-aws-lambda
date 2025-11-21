"""
Async AWS Lambda - A lightweight, zero-dependency library for building async AWS Lambda functions.

This library provides decorators, context managers, and utilities for building async AWS Lambda
functions with optional database support, configuration management, lifecycle management, and error handling.

Core Features:
- @lambda_handler decorator for async Lambda handlers (zero dependencies)
- Optional @with_database decorator for database support (requires [db] extra)
- Optional @with_config decorator for configuration management (requires [config] extra)
- Optional error handling framework
- Lifecycle management for proper resource cleanup

Example:
    # Minimal handler (no dependencies)
    from async_aws_lambda import lambda_handler

    @lambda_handler
    async def handler(event, context):
        return {"statusCode": 200, "body": "Hello"}

    # With database support
    from async_aws_lambda import lambda_handler, with_database
    from sqlalchemy.ext.asyncio import AsyncSession

    @lambda_handler
    @with_database
    async def handler(event, context, db_session: AsyncSession):
        # Database available here
        return {"statusCode": 200}
"""

__version__ = "0.1.0"

# Core exports - always available (zero dependencies)
from .handlers.decorators import lambda_handler
from .handlers.protocols import LambdaHandler

__all__ = [
    "lambda_handler",
    "LambdaHandler",
]

# Optional exports - decorators are always available (raise ImportError if deps missing)
try:
    from .handlers.decorators import with_database
    __all__.append("with_database")
except ImportError:
    pass

try:
    from .handlers.decorators import with_config
    __all__.append("with_config")
except ImportError:
    pass

# Optional module exports
try:
    from .database import get_db_session, init_db, close_db, Base
    __all__.extend(["get_db_session", "init_db", "close_db", "Base"])
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

try:
    from .config import get_settings, Settings
    __all__.extend(["get_settings", "Settings"])
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

try:
    from .errors import ErrorHandler, ProcessingError, ProcessingResult
    __all__.extend(["ErrorHandler", "ProcessingError", "ProcessingResult"])
    HAS_ERRORS = True
except ImportError:
    HAS_ERRORS = False

