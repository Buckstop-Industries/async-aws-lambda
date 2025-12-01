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
    """
    Centralized error handling for Lambda functions.

    This class provides comprehensive error handling, classification, and retry
    logic for Lambda functions. It automatically categorizes errors, determines
    retry strategies, and tracks error statistics.

    Features:
        - Automatic error classification by type
        - Configurable retry logic with exponential backoff
        - Error tracking and statistics
        - Critical error detection and tracking
        - Support for custom retry functions

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Base delay between retries in seconds (default: 1.0)
        error_counts: Dictionary tracking error counts by category
        critical_errors: List of critical errors encountered

    Example:
        Basic usage::

            error_handler = ErrorHandler(max_retries=3, retry_delay=1.0)

            try:
                # Your code here
                result = await some_operation()
            except Exception as e:
                error = error_handler.classify_error(e, context={"key": "value"})
                if error_handler.should_retry(error):
                    # Retry logic
                    await error_handler.handle_error(e, retry_func=some_operation)

        With retry logic::

            async def process_data():
                # Operation that might fail
                return await api_call()

            error_handler = ErrorHandler(max_retries=5, retry_delay=2.0)

            try:
                result = await process_data()
            except Exception as e:
                error = await error_handler.handle_error(
                    e,
                    context={"operation": "process_data"},
                    retry_func=process_data
                )
                if not error.is_recoverable:
                    # Handle non-recoverable error
                    logger.critical(f"Non-recoverable error: {error.message}")
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """
        Initialize error handler.

        Args:
            max_retries: Maximum number of retry attempts. Default is 3.
                Set to 0 to disable retries.
            retry_delay: Base delay between retries in seconds. Default is 1.0.
                The actual delay increases with each retry attempt (exponential
                backoff: delay * retry_count).
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

        This method analyzes an exception and determines its category, severity,
        and recoverability. It creates a ProcessingError object with all
        relevant information for error handling and retry logic.

        Error Classification:
            - ValueError -> VALIDATION (MEDIUM severity, recoverable)
            - ConnectionError -> NETWORK (HIGH severity, recoverable)
            - FileNotFoundError -> FILE_PROCESSING (HIGH severity, not recoverable)
            - PermissionError -> SYSTEM (CRITICAL severity, not recoverable)
            - Other exceptions -> SYSTEM (HIGH severity, recoverable)

        Args:
            error: The exception that occurred. Can be any Exception subclass.
            context: Optional dictionary with additional context information
                about the error. This will be included in the ProcessingError
                details field. Useful for debugging and logging.

        Returns:
            ProcessingError object containing:
                - error_id: Unique identifier for this error
                - category: ErrorCategory enum value
                - severity: ErrorSeverity enum value
                - message: String representation of the error
                - details: Context dictionary (if provided)
                - is_recoverable: Boolean indicating if error can be retried
                - timestamp: When the error occurred
                - retry_count: Current retry count (starts at 0)
                - max_retries: Maximum retry attempts (from handler config)

        Example:
            Basic classification::

                try:
                    result = int("not-a-number")
                except ValueError as e:
                    error = error_handler.classify_error(e)
                    assert error.category == ErrorCategory.VALIDATION
                    assert error.severity == ErrorSeverity.MEDIUM
                    assert error.is_recoverable is True

            With context::

                try:
                    await process_file("data.txt")
                except FileNotFoundError as e:
                    error = error_handler.classify_error(
                        e,
                        context={"filename": "data.txt", "user_id": 123}
                    )
                    assert error.category == ErrorCategory.FILE_PROCESSING
                    assert error.details["filename"] == "data.txt"
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

        This method evaluates whether an error meets the criteria for retry:
        - Error must be recoverable (is_recoverable == True)
        - Retry count must be less than max_retries
        - Error severity must not be CRITICAL

        Args:
            error: The ProcessingError object to evaluate. Must have been
                created by classify_error() or manually constructed with
                appropriate fields.

        Returns:
            True if the error should be retried, False otherwise.

        Example:
            Check before retrying::

                error = error_handler.classify_error(some_exception)
                if error_handler.should_retry(error):
                    # Perform retry logic
                    await retry_operation()
                else:
                    # Handle as final failure
                    logger.error(f"Max retries reached: {error.message}")
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
        Handle an error with automatic retry logic.

        This method classifies the error, logs it appropriately based on severity,
        and optionally retries the operation if a retry function is provided and
        the error is recoverable.

        The retry logic uses exponential backoff: delay = retry_delay * retry_count.
        For example, with retry_delay=1.0:
        - First retry: 1 second delay
        - Second retry: 2 seconds delay
        - Third retry: 3 seconds delay

        Args:
            error: The exception that occurred. Will be classified automatically.
            context: Optional dictionary with additional context information
                about the error. Included in error details for debugging.
            retry_func: Optional async callable to retry if the error is
                recoverable. If provided and should_retry() returns True, this
                function will be called after the delay. The function should
                be the same operation that failed initially.

        Returns:
            ProcessingError object after handling. The retry_count field will
            be updated if retries were attempted. If retry_func is provided
            and succeeds, the error is still returned but the operation completed.

        Raises:
            Any exception raised by retry_func will be caught and logged, but
            the retry loop will continue if max_retries has not been reached.

        Note:
            - Errors are automatically logged based on severity:
              CRITICAL -> critical, HIGH -> error, MEDIUM -> warning, LOW -> info
            - Critical errors are tracked in the critical_errors list
            - Error counts by category are tracked in error_counts
            - Retries only occur if retry_func is provided and should_retry()
              returns True

        Example:
            Basic error handling::

                async def api_call():
                    # Operation that might fail
                    return await http_client.get("https://api.example.com")

                error_handler = ErrorHandler(max_retries=3, retry_delay=1.0)

                try:
                    result = await api_call()
                except Exception as e:
                    error = await error_handler.handle_error(
                        e,
                        context={"endpoint": "https://api.example.com"},
                        retry_func=api_call
                    )
                    if error.retry_count >= error.max_retries:
                        # All retries exhausted
                        logger.error("Operation failed after retries")

            Without retry function::

                try:
                    result = await process_data()
                except Exception as e:
                    # Just classify and log, no retry
                    error = await error_handler.handle_error(
                        e,
                        context={"data_id": 123}
                    )
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
        Get summary of all errors encountered by this handler instance.

        This method provides a comprehensive summary of all errors that have been
        processed by this ErrorHandler instance, including counts by category
        and details of critical errors.

        Returns:
            Dictionary containing:
                - total_errors: Total number of errors encountered
                - error_counts_by_category: Dictionary mapping error category
                  names to their counts
                - critical_errors: Number of critical errors encountered
                - critical_error_details: List of dictionaries with details
                  about each critical error (error_id, message, timestamp)

        Note:
            - Statistics are reset when a new ErrorHandler instance is created
            - Only errors processed through classify_error() or handle_error()
              are tracked
            - Useful for monitoring and reporting error patterns

        Example:
            Get error summary::

                error_handler = ErrorHandler()

                # Process some operations...
                try:
                    await operation1()
                except Exception as e:
                    await error_handler.handle_error(e)

                try:
                    await operation2()
                except Exception as e:
                    await error_handler.handle_error(e)

                # Get summary
                summary = error_handler.get_error_summary()
                print(f"Total errors: {summary['total_errors']}")
                print(f"Critical errors: {summary['critical_errors']}")
                for category, count in summary['error_counts_by_category'].items():
                    print(f"{category}: {count}")

            Example output::

                {
                    "total_errors": 5,
                    "error_counts_by_category": {
                        "validation": 2,
                        "network": 3
                    },
                    "critical_errors": 1,
                    "critical_error_details": [
                        {
                            "error_id": "ERR_1234567890_12345",
                            "message": "Permission denied",
                            "timestamp": "2024-01-01T12:00:00Z"
                        }
                    ]
                }
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
