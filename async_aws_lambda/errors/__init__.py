"""
Error handling framework for Lambda functions.

This module provides comprehensive error handling, retry logic, and recovery
mechanisms for Lambda functions.
"""

from .models import (
    ErrorCategory,
    ErrorSeverity,
    ProcessingError,
    ProcessingResult,
)
from .handlers import ErrorHandler
from .recovery import (
    ErrorRecoveryStrategies,
    PartialProcessingRecovery,
)

__all__ = [
    "ErrorCategory",
    "ErrorSeverity",
    "ProcessingError",
    "ProcessingResult",
    "ErrorHandler",
    "ErrorRecoveryStrategies",
    "PartialProcessingRecovery",
]

# Global error handler instance (optional, for convenience)
default_error_handler = ErrorHandler()

