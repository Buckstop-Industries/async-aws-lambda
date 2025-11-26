"""
Error handling framework for Lambda functions.

This module provides comprehensive error handling and retry logic
for Lambda functions.
"""

from .models import (
    ErrorCategory,
    ErrorSeverity,
    ProcessingError,
    ProcessingResult,
)
from .handlers import ErrorHandler

__all__ = [
    "ErrorCategory",
    "ErrorSeverity",
    "ProcessingError",
    "ProcessingResult",
    "ErrorHandler",
]

# Global error handler instance (optional, for convenience)
default_error_handler = ErrorHandler()

