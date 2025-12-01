"""
Error handling framework for Lambda functions.

This module provides comprehensive error handling and retry logic
for Lambda functions.
"""

from .handlers import ErrorHandler
from .models import (
    ErrorCategory,
    ErrorSeverity,
    ProcessingError,
    ProcessingResult,
)

__all__ = [
    "ErrorCategory",
    "ErrorSeverity",
    "ProcessingError",
    "ProcessingResult",
    "ErrorHandler",
]

# Global error handler instance (optional, for convenience)
default_error_handler = ErrorHandler()

