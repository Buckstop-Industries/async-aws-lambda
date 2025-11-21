"""
Error handler with classification and retry logic.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from .models import ErrorCategory, ErrorSeverity, ProcessingError

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling for Lambda functions."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """
        Initialize error handler.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_counts: dict[ErrorCategory, int] = {}
        self.critical_errors: list[ProcessingError] = []

    def classify_error(
        self, error: Exception, context: dict[str, Any] | None = None
    ) -> ProcessingError:
        """
        Classify and categorize an error.

        Args:
            error: The exception that occurred
            context: Additional context information

        Returns:
            ProcessingError with classification
        """
        error_id = f"ERR_{int(time.time())}_{id(error)}"

        # Determine category and severity based on error type
        if isinstance(error, ValueError):
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.MEDIUM
            is_recoverable = True
        elif isinstance(error, ConnectionError):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.HIGH
            is_recoverable = True
        elif isinstance(error, FileNotFoundError):
            category = ErrorCategory.FILE_PROCESSING
            severity = ErrorSeverity.HIGH
            is_recoverable = False
        elif isinstance(error, PermissionError):
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.CRITICAL
            is_recoverable = False
        else:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.HIGH
            is_recoverable = True

        return ProcessingError(
            error_id=error_id,
            category=category,
            severity=severity,
            message=str(error),
            details=context or {},
            is_recoverable=is_recoverable,
        )

    def should_retry(self, error: ProcessingError) -> bool:
        """
        Determine if an error should be retried.

        Args:
            error: The processing error

        Returns:
            True if the error should be retried
        """
        return (
            error.is_recoverable
            and error.retry_count < error.max_retries
            and error.severity != ErrorSeverity.CRITICAL
        )

    async def handle_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        retry_func: Callable[[], Any] | None = None,
    ) -> ProcessingError:
        """
        Handle an error with retry logic.

        Args:
            error: The exception that occurred
            context: Additional context information
            retry_func: Function to retry (if applicable)

        Returns:
            ProcessingError after handling
        """
        processing_error = self.classify_error(error, context)

        # Track error counts
        self.error_counts[processing_error.category] = (
            self.error_counts.get(processing_error.category, 0) + 1
        )

        # Log error based on severity
        if processing_error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {processing_error.message}")
            self.critical_errors.append(processing_error)
        elif processing_error.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {processing_error.message}")
        elif processing_error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {processing_error.message}")
        else:
            logger.info(f"Low severity error: {processing_error.message}")

        # Attempt retry if applicable
        if self.should_retry(processing_error) and retry_func is not None:
            while self.should_retry(processing_error):
                processing_error.retry_count += 1
                logger.info(
                    f"Retrying operation (attempt {processing_error.retry_count})"
                )

                try:
                    await asyncio.sleep(self.retry_delay * processing_error.retry_count)
                    await retry_func()
                    logger.info("Retry successful")
                    return processing_error
                except Exception as retry_error:
                    logger.warning(f"Retry failed: {retry_error}")
                    # Continue the loop to retry again if max retries not reached

        return processing_error

    def get_error_summary(self) -> dict[str, Any]:
        """
        Get summary of all errors encountered.

        Returns:
            Dictionary with error summary
        """
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts_by_category": {
                category.value: count for category, count in self.error_counts.items()
            },
            "critical_errors": len(self.critical_errors),
            "critical_error_details": [
                {
                    "error_id": err.error_id,
                    "message": err.message,
                    "timestamp": (err.timestamp.isoformat() if err.timestamp else None),
                }
                for err in self.critical_errors
            ],
        }
